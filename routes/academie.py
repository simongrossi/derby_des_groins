import random
import time
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from extensions import db, limiter
from models import User
from models.game_data import AcademieScore
from helpers.game_data import get_hangman_words

academie_bp = Blueprint('academie', __name__)

GAME_DURATION = 30  # seconds


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
        top_scores=top_scores,
        game_duration=GAME_DURATION,
    )


@academie_bp.route('/api/academie/start', methods=['POST'])
@limiter.limit('20 per minute')
def academie_start():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False}), 401

    words = get_hangman_words()
    # Pick enough words for a 30s session (40 should be more than enough)
    pool = [w.upper() for w in random.sample(words, min(40, len(words)))]

    session['academie_words'] = pool
    session['academie_start_ts'] = time.time()
    session.modified = True

    return jsonify({
        'ok': True,
        'words': pool,
        'duration': GAME_DURATION,
    })


@academie_bp.route('/api/academie/submit', methods=['POST'])
@limiter.limit('60 per minute')
def academie_submit():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    payload = request.get_json(silent=True) or {}
    words_completed = int(payload.get('words_completed') or 0)
    total_chars = int(payload.get('total_chars') or 0)
    errors = int(payload.get('errors') or 0)

    start_ts = session.get('academie_start_ts')
    word_pool = session.get('academie_words')

    if not start_ts or not word_pool:
        return jsonify({'ok': False, 'error': 'Aucune partie active'}), 400

    time_taken = min(GAME_DURATION + 2, max(0.1, time.time() - start_ts))

    # Scoring algorithm
    # Base: chars typed correctly
    char_score = total_chars * 10
    # Word completion bonus: each full word = bonus based on its length
    word_bonus = words_completed * 50
    # Speed: chars per second normalized
    cps = total_chars / time_taken if time_taken > 0 else 0
    speed_bonus = int(cps * 100)
    # Error penalty
    error_penalty = errors * 30
    # Accuracy bonus: if few errors relative to chars
    accuracy = max(0, (total_chars - errors)) / max(1, total_chars)
    accuracy_bonus = int(accuracy * 200)

    final_score = int(max(0, char_score + word_bonus + speed_bonus + accuracy_bonus - error_penalty))

    wpm = (words_completed / time_taken) * 60 if time_taken > 0 else 0

    # Build summary label for the leaderboard
    summary = f"{words_completed} mots · {total_chars} car."

    new_score = AcademieScore(
        user_id=user_id,
        word=summary,
        time_taken=round(time_taken, 1),
        errors=errors,
        score=final_score,
    )
    db.session.add(new_score)
    db.session.commit()

    session.pop('academie_words', None)
    session.pop('academie_start_ts', None)
    session.modified = True

    return jsonify({
        'ok': True,
        'score': final_score,
        'words_completed': words_completed,
        'total_chars': total_chars,
        'errors': errors,
        'wpm': round(wpm, 1),
        'accuracy': round(accuracy * 100, 1),
        'time_taken': round(time_taken, 1),
    })
