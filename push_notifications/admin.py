from django.conf.urls import patterns, url
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from .models import APNSDevice, GCMDevice, get_expired_tokens, ADMDevice, ADMToken, request_message_token
from django.db import connection


User = get_user_model()


class DeviceAdmin(admin.ModelAdmin):
	list_display = ("__str__", "device_id", "user", "active", "date_created")
	search_fields = ("name", "device_id", "user__%s" % (User.USERNAME_FIELD))
	list_filter = ("active",)
	actions = (
		"send_message", "send_bulk_message", "prune_devices", "enable", "disable")

	def send_message(self, request, queryset):
		ret = []
		errors = []
		r = ""
		for device in queryset:
			try:
				r = device.send_message("Test single notification")
			except Exception as e:
				errors.append(str(e))
			if r:
				ret.append(r)
		if errors:
			self.message_user(request, _(
				"Some messages could not be processed: %r" % (
					"\n".join(errors))))
		if ret:
			self.message_user(request, _(
				"All messages were sent: %s" % ("\n".join(ret))))

	send_message.short_description = _("Send test message")

	def send_bulk_message(self, request, queryset):
		r = queryset.send_message("Test bulk notification")
		self.message_user(request, _("All messages were sent: %s" % (r)))

	send_bulk_message.short_description = _("Send test message in bulk")

	def enable(self, request, queryset):
		queryset.update(active=True)

	enable.short_description = _("Enable selected devices")

	def disable(self, request, queryset):
		queryset.update(active=False)

	disable.short_description = _("Disable selected devices")

	def prune_devices(self, request, queryset):
		# Note that when get_expired_tokens() is called, Apple's
		# feedback service resets, so, calling it again won't return
		# the device again (unless a message is sent to it again).  So,
		# if the user doesn't select all the devices for pruning, we
		# could very easily leave an expired device as active.  Maybe
		#  this is just a bad API.
		expired = get_expired_tokens()
		devices = queryset.filter(registration_id__in=expired)
		for d in devices:
			d.active = False
			d.save()


class GCMDeviceAdmin(DeviceAdmin):
	"""
	Inherits from DeviceAdmin to handle displaying gcm device as a hex value
	"""

	def device_id_hex(self, obj):
		if connection.vendor in ("mysql", "sqlite") and obj.device_id:
			return hex(obj.device_id).rstrip("L")
		else:
			return obj.device_id

	device_id_hex.short_description = "Device ID"

	list_display = ("__str__", "device_id_hex", "user", "active", "date_created")


def request_adm_token(self, request):
	result = request_message_token()
	if result:
		self.message_user(request, "Error retrieving messaging token: %s" % result, level=messages.ERROR)
	else:
		self.message_user(request, "Successfully retrieved messaging token")


class ADMDeviceAdmin(DeviceAdmin):
	"""
	Inherits from DeviceAdmin to handle displaying gcm device as a hex value
	"""

	def device_id_hex(self, obj):
		if connection.vendor in ("mysql", "sqlite") and obj.device_id:
			return hex(obj.device_id).rstrip("L")
		else:
			return obj.device_id

	device_id_hex.short_description = "Device ID"

	list_display = ("__str__", "device_id_hex", "user", "active", "date_created")

	def get_urls(self):
		urls = super(ADMDeviceAdmin, self).get_urls()
		my_urls = patterns("", url(r"^request_access_token/$", self.request_access_token))
		return my_urls + urls

	def request_access_token(self, request):
		request_adm_token(self, request)
		return HttpResponseRedirect(request.META["HTTP_REFERER"])


class ADMTokenAdmin(admin.ModelAdmin):
	list_display = ("__str__", "token", "expiration_date", "request_id")
	search_fields = ("token", "expiration_date", "request_id")
	# list_filter = ("active",)

	def get_urls(self):
		urls = super(ADMTokenAdmin, self).get_urls()
		my_urls = patterns("", url(r"^request_access_token/$", self.request_access_token))
		return my_urls + urls

	def request_access_token(self, request):
		request_adm_token(self, request)
		return HttpResponseRedirect(request.META["HTTP_REFERER"])

admin.site.register(APNSDevice, DeviceAdmin)
admin.site.register(GCMDevice, GCMDeviceAdmin)
admin.site.register(ADMDevice, ADMDeviceAdmin)
admin.site.register(ADMToken, ADMTokenAdmin)
