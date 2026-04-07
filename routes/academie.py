import random
import time
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from extensions import db, limiter
from models import User
from models.game_data import AcademieScore
from helpers.game_data import get_hangman_words

academie_bp = Blueprint('academie', __name__)

@academie_bp.route('/academie')
def academie():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
        
    user = User.query.get(user_id)
    top_scores = AcademieScore.query.order_by(AcademieScore.score.desc()).limit(15).all()
    
    return render_template(
        'academie.html',
        user=user,
        active_page='academie',
        top_scores=top_scores
    )

@academie_bp.route('/api/academie/start', methods=['POST'])
@limiter.limit('20 per minute')
def academie_start():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False}), 401
        
    words = get_hangman_words()
    word = random.choice(words).replace(' ', '').upper()
    
    session['academie_active_word'] = word
    session['academie_start_ts'] = time.time() + 3.0
    session.modified = True
    
    return jsonify({
        'ok': True,
        'word': word
    })

@academie_bp.route('/api/academie/submit', methods=['POST'])
@limiter.limit('60 per minute')
def academie_submit():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401
        
    payload = request.get_json(silent=True) or {}
    typed_word = (payload.get('word') or '').strip().upper()
    errors = int(payload.get('errors') or 0)
    
    target_word = session.get('academie_active_word')
    start_ts = session.get('academie_start_ts')
    
    if not target_word or not start_ts:
        return jsonify({'ok': False, 'error': 'Aucune partie active'}), 400
        
    if typed_word != target_word:
        return jsonify({'ok': False, 'error': 'Mot incorrect'}), 400
        
    time_taken = max(0.1, time.time() - start_ts)
    
    clean_word = target_word.replace(' ', '')
    unique_letters = len(set(clean_word))
    difficulty_score = (len(clean_word) * 100) + (unique_letters * 50)
    speed_bonus = max(0, 1000 - (time_taken * 50)) 
    error_penalty = errors * 150
    
    final_score = int(max(0, difficulty_score + speed_bonus - error_penalty))
    
    new_score = AcademieScore(
        user_id=user_id,
        word=target_word,
        time_taken=time_taken,
        errors=errors,
        score=final_score
    )
    db.session.add(new_score)
    db.session.commit()
    
    session.pop('academie_active_word', None)
    session.pop('academie_start_ts', None)
    session.modified = True
    
    return jsonify({
        'ok': True,
        'score': final_score,
        'time_taken': time_taken,
        'errors': errors
    })
