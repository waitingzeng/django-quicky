#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import types

from random import randint
from django.db import models
from django.shortcuts import _get_queryset
from django.db.models import Max
from django.db.models.fields import Field
from django.db.models.fields.related import ForeignRelatedObjectsDescriptor, ReverseManyRelatedObjectsDescriptor, ForeignKey, \
    ReverseSingleRelatedObjectDescriptor
from django.db.models.base import ModelBase


__all__ = ['get_random_objects', 'get_object_or_none', 'patch_model']



def get_random_objects(model=None, queryset=None, count=float('+inf')):
    """
       Get `count` random objects for a model object `model` or from
       a queryset. Returns an iterator that yield one object at a time.

       You model must have an auto increment id for it to work and it should
       be available on the `id` attribute.
    """

    if not queryset:
        try:
            queryset = model.objects.all()
        except AttributeError:
            raise ValueError("You must provide a model or a queryset")

    max_ = queryset.aggregate(Max('id'))['id__max']
    i = 0
    while i < count:
        try:
            yield queryset.get(pk=randint(1, max_))
            i += 1
        except queryset.model.DoesNotExist:
            pass


def get_object_or_none(klass, *args, **kwargs):
    """
        Uses get() to return an object or None if the object does not exist.

        klass may be a Model, Manager, or QuerySet object. All other passed
        arguments and keyword arguments are used in the get() query.
    """
    queryset = _get_queryset(klass)
    try:
        return queryset.get(*args, **kwargs)
    except queryset.model.DoesNotExist:
        return None



def patch_model(model_to_patch, class_to_patch_with):
    """
        Adapted from https://gist.github.com/1402045

        Monkey patch a django model with additional or
        replacement fields and methods.

            - All fields and methods that didn't exist previously are added.

            - Existing methods with the same names are renamed with
              <methodname>__overridden, so there are still accessible,
              then the new ones are added.

            - Existing fields with the same name are deleted and replaced with
              the new fields.

        The class used to patch the model MUST be an old-style class (so
        this may not work with Python 3).

        Example (in your models.py):

            from django.contrib.auth.models import User
            from django_quicky.models import patch_model

            class UserOverride: # we don't need to inherit from anything
                email = models.EmailField(_('e-mail address'), unique=True)
                new_field = models.CharField(_('new field'), max_length=10)

                def save(self, *args, **kwargs):

                    # Call original save() method
                    self.save__overridden(*args, **kwargs)

                    # More custom save

            patch_model(User, UserOverride)

    """

    # The _meta attribute is where the definition of the fields is stored in
    # django model classes.
    patched_meta = getattr(model_to_patch, '_meta')
    field_lists = (patched_meta.local_fields, patched_meta.local_many_to_many)

    for name, obj in class_to_patch_with.__dict__.iteritems():

        # If the attribute is a field, delete any field with the same name.
        if isinstance(obj, Field):

            for field_list in field_lists:

                match = ((i, f) for i, f in enumerate(field_list) if f.name == name)
                try:
                    i, field = match.next()
                    # The creation_counter is used by django to know in
                    # which order the database columns are declared. We
                    # get it to ensure that when we override a field it
                    # will be declared in the same position as before.
                    obj.creation_counter = field.creation_counter
                    field_list.pop(i)
                finally:
                    break

        # Add "__overridden" to method names if they already exist.
        elif isinstance(obj, (types.FunctionType, property,
                               staticmethod, classmethod)):

            # rename the potential old method
            attr = getattr(model_to_patch, name, None)
            if attr:
                setattr(model_to_patch, name + '__overridden', attr)

            # bind the new method to the object
            if isinstance(obj, types.FunctionType):
                obj = types.UnboundMethodType(obj, None, model_to_patch)

        # Add the new field/method name and object to the model.
        model_to_patch.add_to_class(name, obj)


class JSONDataMixin(object):
    full_info_fields = []
    simple_info_fields = []
    show_json_comment = False

    @classmethod
    def find_field(cls, name):
        for field in cls._meta.local_fields:
            if field.name == name:
                return field
        return None

    @classmethod
    def get_full_info_fields(cls):
        return cls.full_info_fields

    @classmethod
    def get_simple_info_fields(cls):
        print '>>>>', cls.full_info_fields
        return cls.simple_info_fields or cls.full_info_fields

    def _get_field_data(self, name):
        extra = 'simple'
        if name.find('.') != -1:
            name, extra = name.split('.')

            is_simple_info = extra != 'full'
        else:
            is_simple_info = getattr(self._state, 'is_simple_info', True)

        field = self.find_field(name)
        if not hasattr(self, name):
            return None
        if field:
            short_desc = field.verbose_name
        else:
            short_desc = ''

        v = getattr(self, name)
        if not v:
            return name, None, short_desc

        if type(v) == types.MethodType:

            if hasattr(v, '__name__'):
                name = v.__name__
            if hasattr(v, 'short_description'):
                short_desc = v.short_description
            v = v()
        else:
            if isinstance(field, models.ForeignKey):
                if extra not in ['simple', 'full']:
                    v = getattr(v, extra, None)
                else:
                    v._state.is_simple_info = is_simple_info
                    v = v.json_data()

            elif repr(v).find('RelatedManager') != -1:
                fks = []
                for x in v.all():
                    x._state.is_simple_info = is_simple_info
                    fks.append(x.json_data())
                v = fks
            else:
                if hasattr(v, '__name__'):
                    name = v.__name__
                if hasattr(v, 'short_description'):
                    short_desc = v.short_description
                if callable(v):
                    v = v()

        return name, v, short_desc

    def _get_fields_data(self, fieldset):
        res = {}
        comments = {}
        for fields in fieldset:
            if isinstance(fields, basestring):
                ret = self._get_field_data(fields)
                if not ret:
                    continue
                res[ret[0]] = ret[1]
                if self.show_json_comment:
                    comments[ret[0]] = ret[2]
            else:
                name, fields = fields
                res[name] = {}
                comments[name] = {}
                for field in fields:
                    ret = self._get_field_data(field)
                    if not ret:
                        continue
                    res[name][ret[0]] = ret[1]
                    if self.show_json_comment:
                        comments[name][ret[0]] = ret[2]

        if self.show_json_comment:
            res['_comments'] = comments
        return res

    def full_info(self):
        return self._get_fields_data(self.__class__.get_full_info_fields())

    def simple_info(self):
        return self._get_fields_data(self.__class__.get_simple_info_fields())

    def simple(self):
        self._state.is_simple_info = True

    def full(self):
        self._state.is_simple_info = False

    def json_data(self):
        if getattr(self._state, 'is_simple_info', True):
            return self.simple_info()
        return self.full_info()


