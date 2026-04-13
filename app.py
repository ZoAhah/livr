from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import get_db, init_db
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'livr-secret-key-local')
init_db()

# ─────────────────────────────────────────────
# TRADUCTIONS
# ─────────────────────────────────────────────
TRANSLATIONS = {
    'fr': {
        'nav_dashboard': 'Dashboard',
        'nav_drivers':   'Livreurs',
        'nav_orders':    'Commandes',
        'nav_about':     'À propos',
        'nav_contact':   'Contact',
        'nav_faq':       'FAQ',
        'nav_logout':    'Déconnexion',
        'available':     'disponible',
        'on_delivery':   'en livraison',
        'delivered':     'livré',
        'preparation':   'préparation',
        'add':           '+ Ajouter',
        'delete':        'Supprimer',
        'assign':        '⚡ Go',
        'mark_delivered':'✓ Livré',
        'on_the_way':    '⟶ En route',
        'mark_available':'✓ Disponible',
        'go_delivery':   '⟶ En livraison',
        'no_driver':     'Aucun dispo',
        'total':         'Total',
        'revenue':       'Chiffre livré',
        'lang_label':    '🇬🇧 EN',
        'trial_banner':  'Essai gratuit — il vous reste {} jour(s). Choisissez un plan pour continuer.',
        'trial_expired': 'Votre essai gratuit est terminé. Choisissez un plan pour continuer.',
        'upgrade':       'Choisir un plan',
    },
    'en': {
        'nav_dashboard': 'Dashboard',
        'nav_drivers':   'Drivers',
        'nav_orders':    'Orders',
        'nav_about':     'About',
        'nav_contact':   'Contact',
        'nav_faq':       'FAQ',
        'nav_logout':    'Log out',
        'available':     'available',
        'on_delivery':   'on delivery',
        'delivered':     'delivered',
        'preparation':   'preparing',
        'add':           '+ Add',
        'delete':        'Delete',
        'assign':        '⚡ Go',
        'mark_delivered':'✓ Delivered',
        'on_the_way':    '⟶ On the way',
        'mark_available':'✓ Available',
        'go_delivery':   '⟶ On delivery',
        'no_driver':     'None available',
        'total':         'Total',
        'revenue':       'Revenue',
        'lang_label':    '🇫🇷 FR',
        'trial_banner':  'Free trial — {} day(s) remaining. Pick a plan to keep going.',
        'trial_expired': 'Your free trial has ended. Choose a plan to continue.',
        'upgrade':       'Choose a plan',
    }
}

@app.context_processor
def inject_globals():
    lang = session.get('lang', 'fr')
    trial_days = None
    trial_expired = False
    if 'user_id' in session and session.get('plan') == 'trial':
        trial_end = session.get('trial_ends_at')
        if trial_end and trial_end != '2000-01-01 00:00:00':
            try:
                end_dt = datetime.strptime(trial_end, '%Y-%m-%d %H:%M:%S')
                delta = (end_dt - datetime.now()).days
                if delta < 0:
                    trial_expired = True
                    trial_days = 0
                else:
                    trial_days = delta + 1
            except:
                pass
    return dict(t=TRANSLATIONS[lang], lang=lang, trial_days=trial_days, trial_expired=trial_expired)

@app.route('/lang/<code>')
def set_lang(code):
    if code in ('fr', 'en'):
        session['lang'] = code
    return redirect(request.referrer or url_for('dashboard'))


# ─────────────────────────────────────────────
# DECORATEUR
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# LANDING & FAQ
# ─────────────────────────────────────────────
@app.route('/')
def landing():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        restaurant   = request.form['restaurant'].strip()
        email        = request.form['email'].strip().lower()
        password     = request.form['password'].strip()
        chosen_plan  = request.form.get('chosen_plan', 'trial')

        # Si plan payant choisi dès l'inscription : pas d'essai gratuit
        if chosen_plan in ('starter', 'standard', 'premium'):
            plan          = chosen_plan
            trial_ends_at = None  # pas d'essai
        else:
            plan          = 'trial'
            trial_ends_at = None  # sera calculé par SQLite DEFAULT

        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            flash('Cet email est déjà utilisé.' if session.get('lang','fr')=='fr' else 'This email is already in use.', 'error')
        else:
            hashed = generate_password_hash(password)
            if plan != 'trial':
                # Plan payant : trial_ends_at à NULL (pas d'essai)
                db.execute(
                    'INSERT INTO users (restaurant, email, password, plan, trial_ends_at) VALUES (?, ?, ?, ?, ?)',
                    (restaurant, email, hashed, plan, '2000-01-01 00:00:00')
                )
            else:
                # Essai gratuit : SQLite DEFAULT gère trial_ends_at = now + 14 jours
                db.execute(
                    'INSERT INTO users (restaurant, email, password) VALUES (?, ?, ?)',
                    (restaurant, email, hashed)
                )
            db.commit()
            user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            session['user_id']       = user['id']
            session['restaurant']    = user['restaurant']
            session['plan']          = user['plan']
            session['trial_ends_at'] = user['trial_ends_at']
            db.close()
            return redirect(url_for('dashboard'))
        db.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password'].strip()
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        db.close()
        if user and check_password_hash(user['password'], password):
            session['user_id']       = user['id']
            session['restaurant']    = user['restaurant']
            session['plan']          = user['plan']
            session['trial_ends_at'] = user['trial_ends_at']
            return redirect(url_for('dashboard'))
        flash('Email ou mot de passe incorrect.' if session.get('lang','fr')=='fr' else 'Incorrect email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    uid = session['user_id']
    db  = get_db()
    total_orders  = db.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,)).fetchone()[0]
    orders_prep   = db.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status='préparation'", (uid,)).fetchone()[0]
    orders_route  = db.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status='en livraison'", (uid,)).fetchone()[0]
    orders_done   = db.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status='livré'", (uid,)).fetchone()[0]
    total_drivers = db.execute("SELECT COUNT(*) FROM drivers WHERE user_id=?", (uid,)).fetchone()[0]
    drivers_dispo = db.execute("SELECT COUNT(*) FROM drivers WHERE user_id=? AND status='disponible'", (uid,)).fetchone()[0]
    drivers_route = db.execute("SELECT COUNT(*) FROM drivers WHERE user_id=? AND status='en livraison'", (uid,)).fetchone()[0]
    revenue       = db.execute("SELECT COALESCE(SUM(amount),0) FROM orders WHERE user_id=? AND status='livré'", (uid,)).fetchone()[0]
    recent_orders = db.execute('''
        SELECT orders.*, drivers.name as driver_name
        FROM orders LEFT JOIN drivers ON orders.driver_id = drivers.id
        WHERE orders.user_id=? ORDER BY orders.id DESC LIMIT 5
    ''', (uid,)).fetchall()
    db.close()
    return render_template('dashboard.html',
        total_orders=total_orders, orders_prep=orders_prep,
        orders_route=orders_route, orders_done=orders_done,
        total_drivers=total_drivers, drivers_dispo=drivers_dispo,
        drivers_route=drivers_route, revenue=revenue,
        recent_orders=recent_orders)


# ─────────────────────────────────────────────
# LIVREURS
# ─────────────────────────────────────────────
@app.route('/livreurs')
@login_required
def livreurs():
    uid = session['user_id']
    db  = get_db()
    drivers = db.execute('SELECT * FROM drivers WHERE user_id=? ORDER BY name', (uid,)).fetchall()
    db.close()
    return render_template('livreurs.html', drivers=drivers)

@app.route('/add_driver', methods=['POST'])
@login_required
def add_driver():
    uid     = session['user_id']
    name    = request.form['name'].strip()
    vehicle = request.form['vehicle'].strip()
    lang    = session.get('lang', 'fr')
    if name and vehicle:
        db = get_db()
        # Limite essai gratuit et plan Starter : 3 livreurs max
        plan = session.get('plan', 'trial')
        if plan in ('trial', 'starter'):
            count = db.execute('SELECT COUNT(*) FROM drivers WHERE user_id=?', (uid,)).fetchone()[0]
            if count >= 3:
                db.close()
                flash(
                    'Essai gratuit : maximum 3 livreurs (plan Starter). Passez au Standard pour en ajouter davantage.' if lang == 'fr'
                    else 'Free trial: maximum 3 drivers (Starter plan). Upgrade to Standard to add more.',
                    'error'
                )
                return redirect(url_for('livreurs'))
        db.execute('INSERT INTO drivers (user_id, name, vehicle) VALUES (?, ?, ?)', (uid, name, vehicle))
        db.commit()
        db.close()
    return redirect(url_for('livreurs'))

@app.route('/toggle_status/<int:driver_id>', methods=['POST'])
@login_required
def toggle_status(driver_id):
    uid = session['user_id']
    db  = get_db()
    driver = db.execute('SELECT * FROM drivers WHERE id=? AND user_id=?', (driver_id, uid)).fetchone()
    new_status = None
    if driver:
        new_status = 'en livraison' if driver['status'] == 'disponible' else 'disponible'
        db.execute('UPDATE drivers SET status=? WHERE id=?', (new_status, driver_id))
        db.commit()
    db.close()
    return jsonify({'status': new_status})

@app.route('/delete_driver/<int:driver_id>')
@login_required
def delete_driver(driver_id):
    uid = session['user_id']
    db  = get_db()
    db.execute('DELETE FROM drivers WHERE id=? AND user_id=?', (driver_id, uid))
    db.commit()
    db.close()
    return redirect(url_for('livreurs'))


# ─────────────────────────────────────────────
# COMMANDES
# ─────────────────────────────────────────────
@app.route('/commandes')
@login_required
def commandes():
    uid = session['user_id']
    db  = get_db()
    orders = db.execute('''
        SELECT orders.*, drivers.name as driver_name
        FROM orders LEFT JOIN drivers ON orders.driver_id = drivers.id
        WHERE orders.user_id=? ORDER BY orders.id DESC
    ''', (uid,)).fetchall()
    available_drivers = db.execute(
        "SELECT * FROM drivers WHERE user_id=? AND status='disponible' ORDER BY name", (uid,)
    ).fetchall()
    db.close()
    return render_template('commandes.html', orders=orders, available_drivers=available_drivers)

@app.route('/add_order', methods=['POST'])
@login_required
def add_order():
    uid     = session['user_id']
    client  = request.form['client'].strip()
    address = request.form['address'].strip()
    phone   = request.form['phone'].strip()
    amount  = request.form['amount'].strip()
    payment = request.form['payment'].strip()
    if client and address and phone and amount and payment:
        db = get_db()
        db.execute('INSERT INTO orders (user_id, client, address, phone, amount, payment) VALUES (?,?,?,?,?,?)',
                   (uid, client, address, phone, float(amount), payment))
        db.commit()
        db.close()
    return redirect(url_for('commandes'))

@app.route('/assign_order/<int:order_id>', methods=['POST'])
@login_required
def assign_order(order_id):
    uid       = session['user_id']
    driver_id = request.form['driver_id']
    db = get_db()
    db.execute("UPDATE orders SET driver_id=?, status='en livraison' WHERE id=? AND user_id=?",
               (driver_id, order_id, uid))
    db.execute("UPDATE drivers SET status='en livraison' WHERE id=? AND user_id=?", (driver_id, uid))
    db.commit()
    db.close()
    return redirect(url_for('commandes'))

@app.route('/update_order_status/<int:order_id>/<status>')
@login_required
def update_order_status(order_id, status):
    uid = session['user_id']
    db  = get_db()
    order = db.execute('SELECT * FROM orders WHERE id=? AND user_id=?', (order_id, uid)).fetchone()
    if status == 'en livraison' and (not order or not order['driver_id']):
        db.close()
        return redirect(url_for('commandes'))
    db.execute('UPDATE orders SET status=? WHERE id=?', (status, order_id))
    if status == 'livré' and order and order['driver_id']:
        db.execute("UPDATE drivers SET status='disponible' WHERE id=?", (order['driver_id'],))
    db.commit()
    db.close()
    return redirect(url_for('commandes'))

@app.route('/delete_order/<int:order_id>')
@login_required
def delete_order(order_id):
    uid = session['user_id']
    db  = get_db()
    order = db.execute('SELECT * FROM orders WHERE id=? AND user_id=?', (order_id, uid)).fetchone()
    if order and order['driver_id'] and order['status'] == 'en livraison':
        db.execute("UPDATE drivers SET status='disponible' WHERE id=?", (order['driver_id'],))
    db.execute('DELETE FROM orders WHERE id=? AND user_id=?', (order_id, uid))
    db.commit()
    db.close()
    return redirect(url_for('commandes'))


# ─────────────────────────────────────────────
# CONTACT & A PROPOS
# ─────────────────────────────────────────────
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    sent = False
    if request.method == 'POST':
        name    = request.form['name'].strip()
        email   = request.form['email'].strip()
        message = request.form['message'].strip()
        if name and email and message:
            db = get_db()
            db.execute('INSERT INTO contacts (name, email, message) VALUES (?,?,?)', (name, email, message))
            db.commit()
            db.close()
            sent = True
    return render_template('contact.html', sent=sent)

@app.route('/apropos')
def apropos():
    return render_template('apropos.html')


if __name__ == '__main__':
    app.run(debug=True)
