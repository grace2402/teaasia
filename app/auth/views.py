# app/auth/views.py

from flask import render_template, redirect, request, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from ..models import Catalog, User, Role
from . import auth
from .. import db
from ..email import send_email
from .forms import LoginForm, RegistrationForm, ChangePasswordForm, ChangeAddForm
from .forms import PasswordResetRequestForm, PasswordResetForm, ChangeEmailForm


@auth.before_app_request
def before_request():
    if current_user.is_authenticated \
            and not current_user.confirmed \
            and request.endpoint \
            and request.endpoint[:5] != 'auth.' \
            and request.endpoint != 'static':
        return redirect(url_for('auth.unconfirmed'))


@auth.route('/unconfirmed')
def unconfirmed():
    catalogs = Catalog.get_all()
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('main.index'))
    return render_template('auth/unconfirmed.html', catalogs=catalogs)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    # If Google OAuth is configured, redirect to Google sign-in
    google_oauth = current_app.extensions.get('google_oauth')
    if google_oauth:
        from urllib.parse import urlencode
        
        # Prevent infinite loop: strip next=/auth/logout before redirecting to Google
        next_param = request.args.get('next', '') or ''
        if '/auth/logout' in next_param:
            next_param = url_for('main.index')

        redirect_uri = url_for('auth.google_callback', _external=True)
        return google_oauth.google.authorize_redirect(redirect_uri)

    # Fallback to email/password (should not happen in production)
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            # Prevent redirect to logout in fallback path too
            next_url = request.args.get('next', '') or ''
            if '/auth/logout' in next_url:
                next_url = url_for('main.index')
            return redirect(next_url)
        flash('Invalid username or password.')
    catalogs = Catalog.get_all()
    return render_template('auth/login.html', form=form, catalogs=catalogs)


@auth.route('/google/callback')
def google_callback():
    google_oauth = current_app.extensions.get('google_oauth')
    if not google_oauth:
        flash('Google OAuth 未設定，請聯繫管理員。', 'error')
        return redirect(url_for('auth.login'))

    try:
        token = google_oauth.google.authorize_access_token()
    except Exception as e:
        current_app.logger.error(f"Google OAuth callback failed: {e}")
        flash('Google 登入失敗，請重試。', 'error')
        return redirect(url_for('auth.login'))

    if not token or 'userinfo' not in token:
        flash('Google 登入失敗：未收到使用者資訊。', 'error')
        return redirect(url_for('auth.login'))

    userinfo = token['userinfo']
    email = userinfo.get('email', '')
    
    if not email:
        flash('Google 登入失敗：無法取得 Email。', 'error')
        return redirect(url_for('auth.login'))

    # Find or create user by email
    user = User.query.filter_by(email=email).first()
    if user is None:
        # Auto-create user on first login
        role = Role.query.filter_by(id=2).first()  # Default to user role
        user = User(
            username=userinfo.get('name', email.split('@')[0]),
            email=email,
            phone='',
            add='',
            role_id=role.id if role else 2,
            password_hash='oauth_user'  # Placeholder for OAuth users
        )
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return redirect(request.args.get('next') or url_for('main.index'))


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已登出。')
    return redirect(url_for('auth.login'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # 建立 User 物件，並利用 password setter 產生密碼雜湊
        user = User(
            email=form.email.data,
            phone=form.phone.data,
            add=form.add.data,
            role_id=2,  # 註冊使用者預設 role_id 為 2，可依需求調整
            username=form.username.data,
            password=form.password.data
        )
        db.session.add(user)
        db.session.commit()
        # 透過 refresh 讓 user 物件取得資料庫自動產生的 id
        db.session.refresh(user)

        # 確保 SECRET_KEY 為字串，避免 itsdangerous 處理時發生型別錯誤
        current_app.config['SECRET_KEY'] = str(current_app.config['SECRET_KEY'])
        token = user.generate_confirmation_token()

        send_email(user.email, 'Confirm Your Account', 'auth/email/confirm',
                   user=user, token=token, _external=True)
        flash('A confirmation email has been sent to you by email.')
        return redirect(url_for('auth.login'))
    catalogs = Catalog.get_all()
    return render_template('auth/register.html', form=form, catalogs=catalogs)


@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm(token):
        flash('You have confirmed your account. Thanks!')
    else:
        flash('The confirmation link is invalid or has expired.')
    return redirect(url_for('main.index'))


@auth.route('/confirm')
@login_required
def resend_confirmation():
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, 'Confirm Your Account', 'auth/email/confirm',
               user=current_user, token=token)
    flash('A new confirmation email has been sent to you by email.')
    return redirect(url_for('main.index'))


@auth.route('/change-add', methods=['GET', 'POST'])
@login_required
def change_add():
    form = ChangeAddForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            current_user.add = form.add.data
            db.session.add(current_user)
            flash('Your address has been updated.')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid password.')
    catalogs = Catalog.get_all()
    return render_template("auth/change_add.html", form=form, catalogs=catalogs)


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.password.data
            db.session.add(current_user)
            flash('Your password has been updated.')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid password.')
    catalogs = Catalog.get_all()
    return render_template("auth/change_password.html", form=form, catalogs=catalogs)


@auth.route('/reset', methods=['GET', 'POST'])
def password_reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user.generate_reset_token()
            send_email(user.email, 'Reset Your Password',
                       'auth/email/reset_password', user=user, token=token)
        flash('An email with instructions to reset your password has been sent to you.')
        return redirect(url_for('auth.login'))
    catalogs = Catalog.get_all()
    return render_template('auth/reset_password.html', form=form, catalogs=catalogs)


@auth.route('/reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = PasswordResetForm()
    if form.validate_on_submit():
        if User.reset_password(token, form.password.data):
            flash('Your password has been updated.')
            return redirect(url_for('auth.login'))
        else:
            return redirect(url_for('main.index'))
    catalogs = Catalog.get_all()
    return render_template('auth/reset_password.html', form=form, catalogs=catalogs)


@auth.route('/change_email', methods=['GET', 'POST'])
@login_required
def change_email_request():
    form = ChangeEmailForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            token = current_user.generate_email_change_token(form.email.data)
            send_email(form.email.data, 'Confirm your email address',
                       'auth/email/change_email', user=current_user, token=token)
            flash('An email with instructions to confirm your new email address has been sent to you.')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid email or password.')
    catalogs = Catalog.get_all()
    return render_template('auth/change_email.html', form=form, catalogs=catalogs)


@auth.route('/change_email/<token>')
@login_required
def change_email(token):
    if current_user.change_email(token):
        flash('Your email address has been updated.')
    else:
        flash('Invalid request.')
    return redirect(url_for('main.index'))
