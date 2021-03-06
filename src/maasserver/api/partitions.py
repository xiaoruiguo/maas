# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Partition`."""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_mandatory_param
from maasserver.enum import NODE_STATUS
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
    NodeStateViolation,
)
from maasserver.forms import (
    AddPartitionForm,
    FormatPartitionForm,
)
from maasserver.forms.filesystem import MountFilesystemForm
from maasserver.models import (
    BlockDevice,
    Partition,
    PartitionTable,
)
from maasserver.permissions import NodePermission
from piston3.utils import rc


DISPLAYED_PARTITION_FIELDS = (
    'system_id',
    'device_id',
    'id',
    'uuid',
    'path',
    'type',
    'size',
    'bootable',
    'filesystem',
    'used_for',
    'tags',
)


def get_partition_by_id_or_name__or_404(partition_id, partition_table):
    """Get the partition by its partition_id or its name.

    :raise Http404: If the partition does not exist.
    """
    try:
        partition = Partition.objects.get_partition_by_id_or_name(
            partition_id, partition_table)
    except Partition.DoesNotExist:
        raise Http404()
    return partition


def raise_error_for_invalid_state_on_allocated_operations(
        node, user, operation):
    if node.status not in [NODE_STATUS.READY, NODE_STATUS.ALLOCATED]:
        raise NodeStateViolation(
            "Cannot %s partition because the node is not Ready "
            "or Allocated." % operation)
    if node.status == NODE_STATUS.READY and not user.is_superuser:
        raise PermissionDenied(
            "Cannot %s partition because you don't have the "
            "permissions on a Ready node." % operation)


class PartitionsHandler(OperationsHandler):
    """Manage partitions on a block device."""
    api_doc_section_name = "Partitions"
    update = delete = None
    fields = DISPLAYED_PARTITION_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return (
            'partitions_handler', ["system_id", "device_id"])

    def read(self, request, system_id, device_id):
        """List all partitions on the block device.

        Returns 404 if the node or the block device are not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.view)
        partition_table = device.partitiontable_set.get()
        if partition_table is None:
            return []
        else:
            return partition_table.partitions.all()

    def create(self, request, system_id, device_id):
        """Create a partition on the block device.

        :param size: The size of the partition. If not specified, all
            available space will be used.
        :param uuid: UUID for the partition. Only used if the partition table
            type for the block device is GPT.
        :param bootable: If the partition should be marked bootable.

        Returns 404 if the node or the block device are not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.admin)
        node = device.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot create partition because the node is not Ready.")
        form = AddPartitionForm(device, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        else:
            return form.save()


class PartitionHandler(OperationsHandler):
    """Manage partition on a block device."""
    api_doc_section_name = "Partitions"
    create = replace = update = None
    model = Partition
    fields = DISPLAYED_PARTITION_FIELDS

    @classmethod
    def filesystem(cls, partition):
        # XXX: This is almost the same as
        # m.api.blockdevices.BlockDeviceHandler.filesystem.
        filesystem = partition.get_effective_filesystem()
        if filesystem is not None:
            return {
                'fstype': filesystem.fstype,
                'label': filesystem.label,
                'uuid': filesystem.uuid,
                'mount_point': filesystem.mount_point,
                'mount_options': filesystem.mount_options,
            }
        else:
            return None

    @classmethod
    def resource_uri(cls, partition=None):
        # See the comment in NodeHandler.resource_uri.
        if partition is None:
            system_id = "system_id"
            device_id = "device_id"
            partition_id = "id"
        else:
            partition_id = partition.id
            block_device = partition.partition_table.block_device
            device_id = block_device.id
            system_id = block_device.node.system_id
        return (
            'partition_handler', (system_id, device_id, partition_id))

    @classmethod
    def system_id(cls, partition):
        block_device = partition.partition_table.block_device
        return block_device.node.system_id

    @classmethod
    def device_id(cls, partition):
        return partition.partition_table.block_device.id

    def read(self, request, system_id, device_id, id):
        """Read partition.

        Returns 404 if the node, block device, or partition are not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.view)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        return get_partition_by_id_or_name__or_404(
            id, partition_table)

    def delete(self, request, system_id, device_id, id):
        """Delete partition.

        Returns 404 if the node, block device, or partition are not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.admin)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            id, partition_table)
        node = device.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot delete block device because the node is not Ready.")
        partition.delete()
        return rc.DELETED

    @operation(idempotent=False)
    def format(self, request, system_id, device_id, id):
        """Format a partition.

        :param fstype: Type of filesystem.
        :param uuid: The UUID for the filesystem.
        :param label: The label for the filesystem.

        Returns 403 when the user doesn't have the ability to format the \
            partition.
        Returns 404 if the node, block device, or partition is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.edit)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            id, partition_table)
        node = device.get_node()
        raise_error_for_invalid_state_on_allocated_operations(
            node, request.user, "format")
        form = FormatPartitionForm(partition, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        else:
            return form.save()

    @operation(idempotent=False)
    def unformat(self, request, system_id, device_id, id):
        """Unformat a partition."""
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.edit)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            id, partition_table)
        node = device.get_node()
        raise_error_for_invalid_state_on_allocated_operations(
            node, request.user, "unformat")
        filesystem = partition.get_effective_filesystem()
        if filesystem is None:
            raise MAASAPIBadRequest("Partition is not formatted.")
        if filesystem.is_mounted:
            raise MAASAPIBadRequest(
                "Filesystem is mounted and cannot be unformatted. Unmount the "
                "filesystem before unformatting the partition.")
        if filesystem.filesystem_group is not None:
            nice_name = filesystem.filesystem_group.get_nice_name()
            raise MAASAPIBadRequest(
                "Filesystem is part of a %s, and cannot be "
                "unformatted. Remove partition from %s "
                "before unformatting the partition." % (nice_name, nice_name))
        filesystem.delete()
        return partition

    @operation(idempotent=False)
    def mount(self, request, system_id, device_id, id):
        """Mount the filesystem on partition.

        :param mount_point: Path on the filesystem to mount.
        :param mount_options: Options to pass to mount(8).

        Returns 403 when the user doesn't have the ability to mount the \
            partition.
        Returns 404 if the node, block device, or partition is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.edit)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            id, partition_table)
        raise_error_for_invalid_state_on_allocated_operations(
            device.get_node(), request.user, "mount")
        filesystem = partition.get_effective_filesystem()
        form = MountFilesystemForm(filesystem, data=request.data)
        if form.is_valid():
            form.save()
            return partition
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def unmount(self, request, system_id, device_id, id):
        """Unmount the filesystem on partition.

        Returns 400 if the partition is not formatted or not currently \
            mounted.
        Returns 403 when the user doesn't have the ability to unmount the \
            partition.
        Returns 404 if the node, block device, or partition is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.edit)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            id, partition_table)
        node = device.get_node()
        raise_error_for_invalid_state_on_allocated_operations(
            node, request.user, "unmount")
        filesystem = partition.get_effective_filesystem()
        if filesystem is None:
            raise MAASAPIBadRequest("Partition is not formatted.")
        if not filesystem.is_mounted:
            raise MAASAPIBadRequest("Filesystem is already unmounted.")
        filesystem.mount_point = None
        filesystem.mount_options = None
        filesystem.save()
        return partition

    @operation(idempotent=False)
    def add_tag(self, request, system_id, device_id, id):
        """Add a tag to partition.

        :param tag: The tag being added.

        Returns 403 when the user doesn't have the ability to add tag.
        Returns 404 if the node, block device, or partition is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.admin)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            id, partition_table)
        partition.add_tag(get_mandatory_param(request.POST, 'tag'))
        partition.save()
        return partition

    @operation(idempotent=False)
    def remove_tag(self, request, system_id, device_id, id):
        """Remove a tag from partition.

        :param tag: The tag being removed.

        Returns 403 when the user doesn't have the ability to add tag.
        Returns 404 if the node, block device, or partition is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NodePermission.admin)
        partition_table = get_object_or_404(
            PartitionTable, block_device=device)
        partition = get_partition_by_id_or_name__or_404(
            id, partition_table)
        partition.remove_tag(get_mandatory_param(request.POST, 'tag'))
        partition.save()
        return partition
