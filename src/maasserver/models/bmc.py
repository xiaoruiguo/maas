# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""BMC objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "BMC",
    ]


from django.db.models import (
    CharField,
    ForeignKey,
    PROTECT,
)
from maasserver import DefaultMeta
from maasserver.fields import JSONObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.logger import get_maas_logger
from provisioningserver.power.schema import (
    POWER_FIELDS_BY_TYPE,
    POWER_PARAMETER_SCOPE,
)


maaslog = get_maas_logger("node")


class BMC(CleanSave, TimestampedModel):
    """A `BMC` represents an existing 'baseboard management controller'.  For
    practical purposes in MAAS, this is any addressable device that can control
    the power state of Nodes. The BMC associated with a Node is the one
    expected to control its power.

    Power parameters that apply to all nodes controlled by a BMC are stored
    here in the BMC. Those that are specific to different Nodes on the same BMC
    are stored in the Node model instances.

    :ivar ip_address: This `BMC`'s IP Address.
    :ivar power_type: The power type defines which type of BMC this is.
        Its value must match a power driver class name.
    :ivar power_parameters: Some JSON containing arbitrary parameters this
        BMC's power driver requires to function.
    :ivar objects: The :class:`BMCManager`.
    """

    class Meta(DefaultMeta):
        unique_together = ("power_type", "power_parameters", "ip_address")

    ip_address = ForeignKey(
        StaticIPAddress, default=None, blank=True, null=True, editable=False,
        on_delete=PROTECT)

    # The possible choices for this field depend on the power types advertised
    # by the rack controllers.  This needs to be populated on the fly, in
    # forms.py, each time the form to edit a node is instantiated.
    power_type = CharField(
        max_length=10, null=False, blank=True, default='')

    # JSON-encoded set of parameters for power control, limited to 32kiB when
    # encoded as JSON. These apply to all Nodes controlled by this BMC.
    power_parameters = JSONObjectField(
        max_length=(2 ** 15), blank=True, default='')

    def __unicode__(self):
        if self.ip_address:
            return "%s (%s)" % (self.id, self.ip_address)
        else:
            return self.id

    def delete(self):
        """Delete this BMC."""
        maaslog.info("%s: Deleting BMC", self.id)
        ip_address = self.ip_address
        super(BMC, self).delete()
        # Delete the related interfaces.
        if ip_address:
            ip_address.delete()

    @staticmethod
    def scope_power_parameters(power_type, power_params):
        """Separate the global, bmc related power_parameters from the local,
        node-specific ones."""
        if not power_type:
            # If there is no power type, treat all params as node params.
            return ({}, power_params)
        power_fields = POWER_FIELDS_BY_TYPE.get(power_type)
        if not power_fields:
            # If there is no parameter info, treat all params as node params.
            return ({}, power_params)
        bmc_params = {}
        node_params = {}
        for param_name in power_params:
            power_field = power_fields.get(param_name)
            if (power_field and
                    power_field.get('scope') == POWER_PARAMETER_SCOPE.BMC):
                bmc_params[param_name] = power_params[param_name]
            else:
                node_params[param_name] = power_params[param_name]
        return (bmc_params, node_params)