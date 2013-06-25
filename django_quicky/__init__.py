#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu


__VERSION__ = "0.5.1"

# we may want to read the __init__ file to get the version outiside
# of the scope of Django and the next imports will fails because
# without any settings.py file provided
from decorators import view, url, urlpatterns, ajax_fail, ajax_success
from utils import setting
from models import get_object_or_none

