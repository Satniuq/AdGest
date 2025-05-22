# app/notifications/forms.py

from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired

class CommentForm(FlaskForm):
    comment_text = TextAreaField('Comentário', validators=[DataRequired()])
    submit = SubmitField('Comentar')


class MarkReadForm(FlaskForm):
    """Formulário vazio só para fornecer o CSRF."""
    pass
