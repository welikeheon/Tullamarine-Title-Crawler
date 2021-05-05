from mongoengine.base.datastructures import EmbeddedDocumentList
from mongoengine.connection import connect
from mongoengine.document import Document, EmbeddedDocument
from mongoengine.fields import EmbeddedDocumentField, ListField, StringField
connect('URLShorter', host='127.0.0.1', port=27017)


class Primary_tags(EmbeddedDocument):
    content = StringField()
    name = StringField(max_length=120)


class Facebook_Og_Tags(EmbeddedDocument):
    title = StringField()
    type = StringField()
    image = StringField()
    url = StringField()


class Twitter_tags(EmbeddedDocumentField):
    card = StringField()
    url = StringField()
    title = StringField()
    description = StringField()
    image = StringField()


class Title(Document):
    endpoint = StringField(max_length=120)
    charset = StringField()
    page_title = StringField()
    primary_meta_tags = ListField(EmbeddedDocumentField(Primary_tags))
    facebook_og_tags = ListField(EmbeddedDocumentField(Facebook_Og_Tags))
    twitter_tags = ListField(EmbeddedDocumentField(Twitter_tags))
