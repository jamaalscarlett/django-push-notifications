import json

from django.core.exceptions import ImproperlyConfigured
from pythonadm import AmazonDeviceMessaging

from . import NotificationError
from .settings import PUSH_NOTIFICATIONS_SETTINGS as SETTINGS
from .models import ADMDevice


class ADMError(NotificationError):
	pass


def initialize_adm():
	client_id = SETTINGS.get("ADM_CLIENT_ID")
	client_secret = SETTINGS.get("ADM_CLIENT_SECRET")
	if not client_id:
		raise ImproperlyConfigured(
			'You need to set PUSH_NOTIFICATIONS_SETTINGS["ADM_CLIENT_ID"] to send messages through ADM.'
		)
	if not client_secret:
		raise ImproperlyConfigured(
			'You need to set PUSH_NOTIFICATIONS_SETTINGS["ADM_CLIENT_SECRET"] to send messages through ADM.'
		)
	return AmazonDeviceMessaging(client_secret, client_id)

adm = None

def adm_send_message(registration_id, data, consolidationKey=None,
                     expiresAfter=60, token=None):
	"""
	"""
	global adm
	if not adm:
		adm = initialize_adm()
	if not token:
		token = adm.request_token()
	if token:
		result = adm.send_message(registration_id, data, token, consolidationKey, expiresAfter, False)
		if result.get('error'):
			if result.get('error') in ['Unregistered', 'InvalidRegistrationId']:
				device = ADMDevice.objects.filter(registration_id=registration_id)
				device.update(active=0)
			else:
				raise ADMError(result)
		# import datetime
		# adm.retry_after = (datetime.datetime.now() + datetime.timedelta(days=1))
	else:
		raise ADMError({'registration_id': registration_id,
		          'error': 'error requesting token'})
	return json.dumps(result)

def adm_send_bulk_message(registration_ids, data, **kwargs):
	"""
	"""
	ret = []
	global adm
	if not adm:
		adm = initialize_adm()
	token = adm.request_token()
	if token:
		for registration_id in registration_ids:
			try:
				ret.append(adm_send_message(registration_id, data, token))
			# we dont want to cancel a bulk send on one error
			except ADMError as e:
				ret.append(adm_send_message(registration_id, data, token))
	else:
		raise ADMError({'registration_id': 'all',
		                'error': 'error requesting token'})
	return ret
