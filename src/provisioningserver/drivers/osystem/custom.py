# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Operating System class used for custom images."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "CustomOS",
    ]

import os

from provisioningserver.config import BOOT_RESOURCES_STORAGE
from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
    )


class CustomOS(OperatingSystem):
    """Custom operating system."""

    name = "custom"
    title = "Custom"

    def get_boot_image_purposes(self, arch, subarch, release, label):
        """Gets the purpose of each boot image."""
        # Custom images can only be used with XINSTALL.
        return [BOOT_IMAGE_PURPOSE.XINSTALL]

    def is_release_supported(self, release):
        """Return True when the release is supported, False otherwise."""
        # All release are supported, since the user uploaded it.
        return True

    def get_default_release(self):
        """Gets the default release to use when a release is not
        explicit."""
        # No default for this OS.
        return ""

    def get_release_title(self, release):
        """Return the title for the given release."""
        # Return the same name, since the cluster does not know about the
        # title of the image. The region will fix the title for the UI.
        return release

    def get_xinstall_parameters(self, arch, subarch, release, label):
        """Returns the xinstall image name and type for given image."""
        path = os.path.join(
            BOOT_RESOURCES_STORAGE, 'current', 'custom',
            arch, subarch, release, label)
        if os.path.exists(os.path.join(path, 'root-dd')):
            return "root-dd", "dd-tgz"
        else:
            return "root-tgz", "tgz"
