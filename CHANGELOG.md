# 0.6.101

## Bug Fixes

- Preserve Odoo 17+ ``/_custom/`` SCSS attachments when running ``remove-web-assets``.
  These attachments store website theme customizations (fonts, colors) set via the website
  builder and were incorrectly deleted during asset cache clears, causing themes to lose
  their font and color settings after a module update or migration.


# 0.6.1

- bakery added: create self running images compatible with kubernetes and aws

# 0.5.45

- added detached mode at run and profiles

# 0.5.39

- specific odoo images branch to be compatible from wodoo to wodoo images
- more precise dependency resolving

# 0.5.31

- setting password equal to user login name

# 0.4.87 - 01.03.2024

    * better updating the queuejob channels

# 0.4.82 - 29.02.2024

    * better updating settings

# 0.4.73 - 25.01.2024

- production notes / hints; ask hostname at restore prod
