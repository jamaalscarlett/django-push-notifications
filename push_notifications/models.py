from __future__ import unicode_literals

from datetime import datetime, timedelta
import json
try:
	from urllib.request import Request, urlopen
	from urllib.parse import urlencode
except ImportError:
	from urllib2 import Request, urlopen
	from urllib import urlencode

from django.conf import settings
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from .fields import HexIntegerField


CLIENT_ID = 'amzn1.application-oa2-client.31e9a7961fce47aebaa9d3ac4ef9c318'
CLIENT_SECRET = '937656fa3477255af004e56d767055423aaefe64260e8495455e02001a14a1bf'

# Data used to request authorization tokens.
ACCESS_TOKEN_REQUEST_DATA = {
	"grant_type": "client_credentials",
	"scope": "messaging:push",
	"client_secret": CLIENT_SECRET,
	"client_id": CLIENT_ID
}


@python_2_unicode_compatible
class Device(models.Model):
	name = models.CharField(max_length=255, verbose_name=_("Name"), blank=True, null=True)
	active = models.BooleanField(verbose_name=_("Is active"), default=True,
		help_text=_("Inactive devices will not be sent notifications"))
	user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True)
	date_created = models.DateTimeField(verbose_name=_("Creation date"), auto_now_add=True, null=True)

	class Meta:
		abstract = True

	def __str__(self):
		return self.name or \
			str(self.device_id or "") or \
			"%s for %s" % (self.__class__.__name__, self.user or "unknown user")


class GCMDeviceManager(models.Manager):
	def get_queryset(self):
		return GCMDeviceQuerySet(self.model)


class GCMDeviceQuerySet(models.query.QuerySet):
	def send_message(self, message, **kwargs):
		if self:
			from .gcm import gcm_send_bulk_message

			data = kwargs.pop("extra", {})
			if message is not None:
				data["message"] = message

			reg_ids = list(self.filter(active=True).values_list('registration_id', flat=True))
			return gcm_send_bulk_message(registration_ids=reg_ids, data=data, **kwargs)


class GCMDevice(Device):
	# device_id cannot be a reliable primary key as fragmentation between different devices
	# can make it turn out to be null and such:
	# http://android-developers.blogspot.co.uk/2011/03/identifying-app-installations.html
	device_id = HexIntegerField(verbose_name=_("Device ID"), blank=True, null=True, db_index=True,
		help_text=_("ANDROID_ID / TelephonyManager.getDeviceId() (always as hex)"))
	registration_id = models.TextField(verbose_name=_("Registration ID"))

	objects = GCMDeviceManager()

	class Meta:
		verbose_name = _("GCM device")

	def send_message(self, message, **kwargs):
		from .gcm import gcm_send_message
		data = kwargs.pop("extra", {})
		if message is not None:
			data["message"] = message
		return gcm_send_message(registration_id=self.registration_id, data=data, **kwargs)


class APNSDeviceManager(models.Manager):
	def get_queryset(self):
		return APNSDeviceQuerySet(self.model)


class APNSDeviceQuerySet(models.query.QuerySet):
	def send_message(self, message, **kwargs):
		if self:
			from .apns import apns_send_bulk_message
			reg_ids = list(self.filter(active=True).values_list('registration_id', flat=True))
			return apns_send_bulk_message(registration_ids=reg_ids, alert=message, **kwargs)


class APNSDevice(Device):
	device_id = models.UUIDField(verbose_name=_("Device ID"), blank=True, null=True, db_index=True,
		help_text="UDID / UIDevice.identifierForVendor()")
	registration_id = models.CharField(verbose_name=_("Registration ID"), max_length=64, unique=True)

	objects = APNSDeviceManager()

	class Meta:
		verbose_name = _("APNS device")

	def send_message(self, message, **kwargs):
		from .apns import apns_send_message

		return apns_send_message(registration_id=self.registration_id, alert=message, **kwargs)


# This is an APNS-only function right now, but maybe GCM will implement it
# in the future.  But the definition of 'expired' may not be the same. Whatevs
def get_expired_tokens():
	from .apns import apns_fetch_inactive_ids
	return apns_fetch_inactive_ids()


class ADMDeviceManager(models.Manager):
	def get_queryset(self):
		return ADMDeviceQuerySet(self.model)


class ADMDeviceQuerySet(models.query.QuerySet):
	def send_message(self, message, **kwargs):
		if self:
			from .adm import adm_send_bulk_message

			data = kwargs.pop("extra", {})
			if message is not None:
				data["message"] = message

			reg_ids = [rec.registration_id for rec in self if rec.active]
			return adm_send_bulk_message(registration_ids=reg_ids, data=data, **kwargs)


class ADMDevice(Device):
	# device_id cannot be a reliable primary key as fragmentation between different devices
	# can make it turn out to be null and such:
	# http://android-developers.blogspot.co.uk/2011/03/identifying-app-installations.html
	device_id = HexIntegerField(verbose_name=_("Device ID"), blank=True, null=True, db_index=True,
								help_text=_("ANDROID_ID / TelephonyManager.getDeviceId() (always as hex)"))
	registration_id = models.TextField(verbose_name=_("Registration ID"))

	objects = ADMDeviceManager()

	class Meta:
		verbose_name = _("ADM device")

	def send_message(self, message, **kwargs):
		from .adm import adm_send_message
		data = kwargs.pop("extra", {})
		if message is not None:
			data["message"] = message
		return adm_send_message(registration_id=self.registration_id, data=data, **kwargs)


class ADMTokenManager(models.Manager):
	def get_queryset(self):
		return ADMTokenQuerySet(self.model)


class ADMTokenQuerySet(models.query.QuerySet):
	pass


@python_2_unicode_compatible
class ADMToken(models.Model):
	token = models.CharField(verbose_name=_("Token"), max_length=80)
	expiration_date = models.DateTimeField()
	request_id = models.CharField(verbose_name=_("Request ID"), max_length=36)

	objects = ADMTokenManager()

	class Meta:
		verbose_name = _("Amazon Device Messaging Access Token")

	def __str__(self):
		return self.request_id


def request_message_token():
	try:
		request = Request("https://api.amazon.com/auth/O2/token")
		request.add_header('Content-Type', 'application/x-www-form-urlencoded')
		req_data = urlencode(ACCESS_TOKEN_REQUEST_DATA)
		response = urlopen(request, req_data)

		request_id = response.info().get('x-amzn-RequestId')
		dump = json.load(response)
		if dump['token_type'] == 'bearer' and dump['scope'] == 'messaging:push':
			token = dump['access_token']
			expiration = dump['expires_in']
			expiration = datetime.now() + timedelta(0, expiration)
			ADMToken(token=token, expiration_date=expiration, request_id=request_id).save()
		else:
			return "Invalid request"
	except Exception as e:
		return e.message
