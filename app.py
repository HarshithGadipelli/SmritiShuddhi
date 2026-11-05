from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
import csv, uuid, time
from datetime import datetime, timezone

import pandas as pd

import config
from db import init_db, news_col, training_col, requests_col, unlearning_col, models_col, actions_col, devices_col, audit_col, now
from utils import normalize_text, serialize_doc
from model_service import Predictor
from unlearning.sisa import unlearn_sample, load_active_ensemble

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')
predictor = Predictor()


def admin_required():
    return session.get('admin') is True

def audit(action, detail=None):
    audit_col.insert_one({'action': action, 'detail': detail or {}, 'created_at': now(), 'actor': session.get('admin_username','system')})

def seed_demo_news():
    path=Path('data/processed/train.csv')
    if not path.exists() or news_col.count_documents({}) > 0:
        return
    df=pd.read_csv(path).head(6).fillna('')
    for _, r in df.iterrows():
        n={
            'news_id': f'NEWS_DEMO_{r.sample_id}',
            'title': str(r.title), 'content': str(r.text),
            'submitted_by':'demo-seed', 'ai_prediction':'', 'fake_probability':None,
            'real_probability':None, 'risk_band':'TRAINING_DEMO',
            'verification_status':'TRAINING_SAMPLE', 'publication_status':'ACTIVE',
            'active':True, 'training_sample_id':str(r.sample_id),
            'created_at':now(), 'updated_at':now(), 'model_version':'demo'
        }
        pred=predictor.predict(n['title'],n['content'])
        n.update(pred)
        news_col.insert_one(n)

def sync_training_registry():
    path=Path('data/processed/train.csv')
    if not path.exists(): return
    df=pd.read_csv(path).fillna('')
    for _, r in df.iterrows():
        training_col.update_one({'sample_id':str(r.sample_id)}, {'$setOnInsert':{
            'sample_id':str(r.sample_id),'news_id':f'TRAIN_{r.sample_id}','title':str(r.title),'text':str(r.text),
            'label':int(r.label),'forget_status':False,'created_at':now()
        }}, upsert=True)

init_db()
sync_training_registry()
seed_demo_news()

@app.route('/')
def index():
    if (Path('templates') / 'enterprise_dashboard.html').exists():
        return render_template('enterprise_dashboard.html')
    return render_template('index.html')

@app.route('/admin')
def admin(): return render_template('admin.html')

@app.route('/login', methods=['POST'])
def login():
    username=request.form.get('username','')
    password=request.form.get('password','')
    if username==config.ADMIN_USERNAME and password==config.ADMIN_PASSWORD:
        session['admin']=True; session['admin_username']=username
        return redirect(url_for('admin'))
    return render_template('login.html', error='Invalid credentials')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('index'))

@app.get('/api/news')
def get_news():
    limit=min(int(request.args.get('limit',50)),200)
    docs=[serialize_doc(x) for x in news_col.find({'active':True}).sort('created_at',-1).limit(limit)]
    return jsonify(docs)

@app.post('/api/news')
def submit_news():
    data=request.get_json(force=True)
    title=normalize_text(data.get('title',''))
    content=normalize_text(data.get('content',''))
    if len(title)+len(content)<20: return jsonify({'error':'Please provide a meaningful title and article body.'}),400
    pred=predictor.predict(title,content)
    news_id='NEWS_'+uuid.uuid4().hex[:12]
    doc={
        'news_id':news_id,'title':title,'content':content,
        'submitted_by':data.get('user_id','anonymous'),'created_at':now(),'updated_at':now(),
        'active':True,'publication_status':'ACTIVE' if pred['risk_band']!='HIGH_RISK_FAKE' else 'PENDING_ADMIN',
        'verification_status':'AI_ONLY','training_sample_id':None,
        **pred
    }
    news_col.insert_one(doc)
    devices_col.update_many({}, {'$set':{'last_seen_event':now()}})
    socketio.emit('news_created', serialize_doc(doc))
    if pred['risk_band']=='HIGH_RISK_FAKE':
        socketio.emit('admin_alert', {'type':'HIGH_RISK_FAKE','news':serialize_doc(doc)})
    else:
        socketio.emit('news_published', serialize_doc(doc))
    audit('NEWS_SUBMITTED', {'news_id':news_id,'prediction':pred})
    return jsonify(serialize_doc(doc))

@app.post('/api/news/<news_id>/report')
def report_news(news_id):
    data=request.get_json(force=True)
    req={
        'request_id':'REQ_'+uuid.uuid4().hex[:12],'news_id':news_id,'requested_by':data.get('user_id','anonymous'),
        'request_type':data.get('reason','OTHER'),'description':data.get('description',''),
        'status':'PENDING','created_at':now(),'resolved_at':None,'admin_decision':None
    }
    requests_col.insert_one(req)
    socketio.emit('admin_alert', {'type':'REMOVAL_REQUEST','request':serialize_doc(req)})
    return jsonify(serialize_doc(req))

@app.get('/api/admin/requests')
def admin_requests():
    if not admin_required(): return jsonify({'error':'Unauthorized'}),401
    docs=[serialize_doc(x) for x in requests_col.find().sort('created_at',-1).limit(100)]
    return jsonify(docs)

@app.get('/api/admin/high-risk')
def admin_high_risk():
    if not admin_required(): return jsonify({'error':'Unauthorized'}),401
    docs=[serialize_doc(x) for x in news_col.find({'risk_band':'HIGH_RISK_FAKE','active':True}).sort('created_at',-1).limit(100)]
    return jsonify(docs)

@app.get('/api/admin/status')
def admin_status():
    if not admin_required(): return jsonify({'error':'Unauthorized'}),401
    try:
        ens=load_active_ensemble(config.SISA_DIR)
        model_version=ens.version_id
    except Exception:
        model_version='none'
    return jsonify({
        'model_version':model_version,
        'news_count':news_col.count_documents({'active':True}),
        'high_risk_count':news_col.count_documents({'risk_band':'HIGH_RISK_FAKE','active':True}),
        'request_count':requests_col.count_documents({'status':'PENDING'}),
        'connected_devices':devices_col.count_documents({'online':True})
    })

@app.post('/api/admin/news/<news_id>/decision')
def decide_news(news_id):
    if not admin_required(): return jsonify({'error':'Unauthorized'}),401
    data=request.get_json(force=True)
    decision=data.get('decision')
    doc=news_col.find_one({'news_id':news_id})
    if not doc: return jsonify({'error':'News not found'}),404
    if decision=='keep':
        news_col.update_one({'news_id':news_id},{'$set':{'verification_status':'ADMIN_KEPT','publication_status':'ACTIVE','updated_at':now()}})
        socketio.emit('news_updated', {'news_id':news_id,'status':'ACTIVE'})
        audit('ADMIN_KEEP', {'news_id':news_id})
        return jsonify({'status':'kept'})
    if decision=='remove':
        news_col.update_one({'news_id':news_id},{'$set':{'verification_status':'ADMIN_REMOVED','publication_status':'REVOKED','active':False,'updated_at':now()}})
        socketio.emit('news_revoked', {'news_id':news_id,'reason':'ADMIN_REMOVE'})
        audit('ADMIN_REMOVE', {'news_id':news_id})
        return jsonify({'status':'removed','model_unlearning':'not_requested'})
    if decision=='unlearn':
        return perform_unlearning(news_id)
    return jsonify({'error':'decision must be keep, remove or unlearn'}),400

@app.post('/api/admin/unlearn/<news_id>')
def api_unlearn(news_id):
    if not admin_required(): return jsonify({'error':'Unauthorized'}),401
    return perform_unlearning(news_id)


def perform_unlearning(news_id):
    doc=news_col.find_one({'news_id':news_id})
    if not doc: return jsonify({'error':'News not found'}),404
    sample_id=doc.get('training_sample_id')
    job_id='JOB_'+uuid.uuid4().hex[:12]
    created=now()
    job={'job_id':job_id,'news_id':news_id,'sample_id':sample_id,'status':'RUNNING','created_at':created}
    unlearning_col.insert_one(job)
    try:
        if not sample_id:
            news_col.update_one({'news_id':news_id},{'$set':{'verification_status':'ADMIN_REMOVED','publication_status':'REVOKED','active':False,'updated_at':now()}})
            unlearning_col.update_one({'job_id':job_id},{'$set':{'status':'COMPLETED_CONTENT_ONLY','completed_at':now(),'reason':'News was not a registered training sample.'}})
            socketio.emit('news_revoked', {'news_id':news_id,'reason':'CONTENT_ONLY','job_id':job_id})
            audit('CONTENT_REVOKED_NO_MODEL_UNLEARNING', {'news_id':news_id,'job_id':job_id})
            return jsonify({'status':'content_removed','model_unlearning':False,'job_id':job_id})
        new_version=f'v{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}'
        manifest, seconds=unlearn_sample(config.SISA_DIR,str(sample_id),new_version)
        predictor.reload()
        models_col.insert_one({'version_id':new_version,'type':'sisa','created_at':now(),'unlearning_job':job_id,'affected_shard':manifest.get('affected_shard'),'affected_slice':manifest.get('affected_slice'),'unlearning_seconds':seconds})
        training_col.update_one({'sample_id':str(sample_id)},{'$set':{'forget_status':True,'forgotten_at':now(),'forget_job_id':job_id}})
        news_col.update_one({'news_id':news_id},{'$set':{'verification_status':'UNLEARNED_AND_REVOKED','publication_status':'REVOKED','active':False,'updated_at':now(),'unlearned_model_version':new_version}})
        unlearning_col.update_one({'job_id':job_id},{'$set':{'status':'COMPLETED','completed_at':now(),'new_model_version':new_version,'seconds':seconds,'affected_shard':manifest.get('affected_shard'),'affected_slice':manifest.get('affected_slice')}})
        socketio.emit('model_updated', {'version_id':new_version,'job_id':job_id})
        socketio.emit('news_revoked', {'news_id':news_id,'reason':'UNLEARNED_AND_REVOKED','job_id':job_id})
        audit('UNLEARN_COMPLETED', {'news_id':news_id,'sample_id':sample_id,'new_model_version':new_version,'seconds':seconds})
        return jsonify({'status':'unlearned_and_removed','job_id':job_id,'new_model_version':new_version,'seconds':seconds,'affected_shard':manifest.get('affected_shard'),'affected_slice':manifest.get('affected_slice')})
    except Exception as exc:
        unlearning_col.update_one({'job_id':job_id},{'$set':{'status':'FAILED','completed_at':now(),'error':str(exc)}})
        audit('UNLEARN_FAILED', {'news_id':news_id,'job_id':job_id,'error':str(exc)})
        return jsonify({'status':'failed','job_id':job_id,'error':str(exc)}),500

@socketio.on('connect')
def handle_connect():
    client_id=request.args.get('client_id') or uuid.uuid4().hex[:10]
    devices_col.update_one({'client_id':client_id},{'$set':{'client_id':client_id,'online':True,'last_seen':now()}},upsert=True)
    emit('connected', {'client_id':client_id})

@socketio.on('disconnect')
def handle_disconnect():
    pass

if __name__=='__main__':
    socketio.run(app,host=config.HOST,port=config.PORT,debug=True,allow_unsafe_werkzeug=True)
