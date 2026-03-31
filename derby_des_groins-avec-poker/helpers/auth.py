from functools import wraps
from flask import session, redirect, url_for, request, flash
from models import User

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login', next=request.path))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash("Acces reserve aux administrateurs.", "error")
            return redirect(url_for('main.index'))
        return f(user, *args, **kwargs)
    return decorated_function
