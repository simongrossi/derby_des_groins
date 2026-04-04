from datetime import datetime

from extensions import db


class UserNotification(db.Model):
    __tablename__ = 'user_notification'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False, default='info')
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.String(280), nullable=False)
    event_key = db.Column(db.String(120), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('notifications', lazy=True))


class AuthEventLog(db.Model):
    __tablename__ = 'auth_event_log'

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(40), nullable=False)
    is_success = db.Column(db.Boolean, nullable=False, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    username_attempt = db.Column(db.String(80), nullable=True, index=True)
    ip_address = db.Column(db.String(64), nullable=False, index=True)
    user_agent = db.Column(db.String(300), nullable=True)
    route = db.Column(db.String(120), nullable=True)
    details = db.Column(db.String(255), nullable=True)
    occurred_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('auth_events', lazy=True))

    __table_args__ = (
        db.Index('ix_auth_event_type_time', 'event_type', 'occurred_at'),
    )


class ChatMessage(db.Model):
    __tablename__ = 'chat_message'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('chat_message.id'), nullable=True)

    user = db.relationship('User', backref=db.backref('chat_messages', lazy=True))
    replies = db.relationship('ChatMessage', backref=db.backref('parent', remote_side=[id]), lazy=True)

    def __repr__(self):
        return f'<ChatMessage {self.id} by {self.username}>'

    def to_dict(self):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'message': self.message,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'parent_id': self.parent_id,
        }
        if self.parent:
            data['parent_context'] = {
                'username': self.parent.username,
                'message': self.parent.message[:50] + ('...' if len(self.parent.message) > 50 else ''),
            }
        return data
