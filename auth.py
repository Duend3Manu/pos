from functools import wraps
from flask import session, redirect, url_for

def solo_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Si no hay rol o el rol no es admin, mandar al inicio
        if 'rol' not in session or session['rol'] != 'admin':
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function