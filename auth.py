<<<<<<< HEAD
from functools import wraps
from flask import session, redirect, url_for

def solo_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Si no hay rol o el rol no es admin, mandar al inicio
        if 'rol' not in session or session['rol'] != 'admin':
            return redirect(url_for('home'))
        return f(*args, **kwargs)
=======
from functools import wraps
from flask import session, redirect, url_for

def solo_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Si no hay rol o el rol no es admin, mandar al inicio
        if 'rol' not in session or session['rol'] != 'admin':
            return redirect(url_for('home'))
        return f(*args, **kwargs)
>>>>>>> 0846279f9ea5fd866a5be85c706dab7f5dde2b77
    return decorated_function