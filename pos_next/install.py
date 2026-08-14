"""
Installation and Migration hooks for POS Next

This module relies on Frappe's fixture system for:
- Custom fields (custom_field.json)
- Roles (role.json)
- Custom DocPerm (custom_docperm.json)
- Print formats (print_format.json)

The fixtures are defined in hooks.py and synced automatically during install/migrate.
This module handles post-fixture tasks like setting defaults and clearing cache.
"""

import logging

import frappe

# Configure logger
logger = logging.getLogger(__name__)


def after_install():
	"""Hook that runs after app installation"""
	try:
		log_message("POS Next: Running post-install setup", level="info")

		# Setup default print format for POS Profiles
		setup_default_print_format()

		# Ensure roles that manage POS Profiles can create them
		setup_pos_profile_permissions()

		# Link the POSNext desktop icon to the pos_next app
		setup_desktop_icon()

		# Clear cache to ensure changes take effect
		frappe.clear_cache()
		frappe.db.commit()

		log_message("POS Next: Installation completed successfully", level="success")
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(title="POS Next Installation Error", message=frappe.get_traceback())
		log_message(f"POS Next: Installation error - {e!s}", level="error")
		raise


def after_migrate():
	"""Hook that runs after bench migrate"""
	try:
		# Reclaim POS Settings if ERPNext re-imported its Single on top of ours.
		# Must run in after_migrate (not as a one-shot patch) because ERPNext's
		# doctype sync runs after pos_next's and would overwrite anything we did
		# during pre/post-model-sync.
		reclaim_pos_settings_doctype(quiet=True)

		# Setup default print format
		setup_default_print_format(quiet=True)

		# Ensure roles that manage POS Profiles can create them
		setup_pos_profile_permissions(quiet=True)

		# Link the POSNext desktop icon to the pos_next app
		setup_desktop_icon(quiet=True)

		# Clear cache
		frappe.clear_cache()
		frappe.db.commit()

		log_message("POS Next: Migration completed successfully", level="success")
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(title="POS Next Migration Error", message=frappe.get_traceback())
		log_message(f"POS Next: Migration error - {str(e)}", level="error")
		raise


def setup_default_print_format(quiet=False):
	"""
	Set POS Next Receipt as default print format for POS Profiles if not already set.

	Args:
		quiet (bool): If True, suppress detailed logs
	"""
	try:
		# Check if the print format exists
		if not frappe.db.exists("Print Format", "POS Next Receipt"):
			if not quiet:
				log_message(
					"POS Next Receipt print format not found, skipping default setup", level="warning"
				)
			return

		# Get all POS Profiles without a print format
		pos_profiles = frappe.get_all(
			"POS Profile", filters={"print_format": ["in", ["", None]]}, fields=["name"]
		)

		if pos_profiles:
			updated_count = 0
			for profile in pos_profiles:
				try:
					frappe.db.set_value(
						"POS Profile", profile.name, "print_format", "POS Next Receipt", update_modified=False
					)
					if not quiet:
						log_message(f"Set default print format for: {profile.name}", level="info", indent=1)
					updated_count += 1
				except Exception as e:
					log_message(
						f"Error updating POS Profile {profile.name}: {str(e)}", level="error", indent=1
					)

			if updated_count > 0 and not quiet:
				log_message(
					f"Updated {updated_count} POS Profile(s) with default print format", level="success"
				)

	except Exception as e:
		log_message(f"Error setting up default print format: {str(e)}", level="error")
		frappe.log_error(title="Default Print Format Setup Error", message=frappe.get_traceback())


POS_PROFILE_PERMISSIONS = {
	"Administrator": {
		"create": 1, "read": 1, "write": 1, "report": 1, "export": 1, "delete": 0,
	},
	"System Manager": {
		"create": 1, "read": 1, "write": 1, "report": 1, "export": 1, "delete": 0,
	},
	"Accounts Manager": {
		"create": 1, "read": 1, "write": 1, "report": 1, "export": 1, "delete": 0,
	},
	"Accounts User": {
		"read": 1,
	},
}


def setup_pos_profile_permissions(quiet=False):
	"""
	Ensure roles that manage POS Profiles can create them.

	Frappe v16+ treats `Custom DocPerm` as the authoritative permission
	store. POS Next's fixture only ships a POSNext Cashier row (read-only),
	which prevents `setup_custom_perms` from copying the legacy `tabDocPerm`
	rows — leaving no role with create access and hiding the "+ New" button
	on the POS Profile list.

	Idempotent upsert: skips any existing (role, permlevel, if_owner) row and
	never touches POSNext Cashier rows. Also usable as a repair script:

	    bench --site <site> execute pos_next.install.setup_pos_profile_permissions

	Args:
		quiet (bool): If True, suppress detailed logs

	Returns:
		int: number of permission rows added
	"""
	doctype = "POS Profile"
	existing_rows = {
		(row.role, row.permlevel, row.if_owner)
		for row in frappe.db.sql(
			"""select role, permlevel, if_owner from `tabCustom DocPerm`
			where parent = %s""",
			doctype,
			as_dict=True,
		)
	}

	added = 0
	for role, perms in POS_PROFILE_PERMISSIONS.items():
		key = (role, 0, 0)
		if key in existing_rows:
			continue

		doc = frappe.new_doc("Custom DocPerm")
		doc.parent = doctype
		doc.parenttype = "DocType"
		doc.parentfield = "permissions"
		doc.role = role
		doc.permlevel = 0
		doc.if_owner = 0
		doc.create = perms.get("create", 0)
		doc.read = perms.get("read", 0)
		doc.write = perms.get("write", 0)
		doc.report = perms.get("report", 0)
		doc.export = perms.get("export", 0)
		doc.delete = perms.get("delete", 0)
		doc.insert(ignore_permissions=True)
		existing_rows.add(key)
		added += 1
		if not quiet:
			log_message(f"Added POS Profile permission for role: {role}", level="info", indent=1)

	if added:
		from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype

		validate_permissions_for_doctype(doctype)
		frappe.clear_cache()

	frappe.db.commit()

	if not quiet:
		log_message(
			f"POS Profile permissions up to date ({added} row(s) added)",
			level="success" if added else "info",
		)
	return added


def verify_pos_profile_permissions():
	"""
	Check that all expected POS Profile permission rows exist and are correct.

	Returns:
		list: missing or mismatched (role, permission) tuples; empty when OK
	"""
	rows = frappe.db.sql(
		"""select role, `create`, `read`, `write`, report, export, `delete`
		from `tabCustom DocPerm`
		where parent = 'POS Profile' and permlevel = 0 and if_owner = 0""",
		as_dict=True,
	)
	by_role = {row.role: row for row in rows}

	missing = []
	for role, perms in POS_PROFILE_PERMISSIONS.items():
		row = by_role.get(role)
		if not row:
			missing.append((role, "row missing"))
			continue
		for ptype, expected in perms.items():
			if row.get(ptype) != expected:
				missing.append((role, ptype))

	return missing


def log_message(message, level="info", indent=0):
	"""
	Standardized logging function with consistent formatting.

	Args:
		message (str): The message to log
		level (str): Log level - info, success, warning, error
		indent (int): Indentation level (0, 1, 2, etc.)
	"""
	indent_str = "  " * indent

	prefixes = {
		"info": "[INFO]",
		"success": "[SUCCESS]",
		"warning": "[WARNING]",
		"error": "[ERROR]",
	}

	prefix = prefixes.get(level, "[INFO]")
	formatted_message = f"{indent_str}{prefix} {message}"

	# Print to console
	print(formatted_message)

	# Also log to frappe logger
	if level == "error":
		logger.error(message)
	elif level == "warning":
		logger.warning(message)
	else:
		logger.info(message)


def setup_desktop_icon(quiet=False):
	"""
	Link the POSNext Desktop Icon record to the pos_next app so the desk
	renders the app icon (assets/pos_next/icons/desktop_icons/...) instead
	of falling back to the label's initial letter.

	Args:
		quiet (bool): If True, suppress detailed logs
	"""
	try:
		if frappe.db.exists("Desktop Icon", "POSNext"):
			if frappe.db.get_value("Desktop Icon", "POSNext", "app") != "pos_next":
				frappe.db.set_value(
					"Desktop Icon", "POSNext", "app", "pos_next", update_modified=False
				)
				if not quiet:
					log_message("Linked POSNext Desktop Icon to pos_next app", level="info")
		else:
			frappe.get_doc(
				{
					"doctype": "Desktop Icon",
					"label": "POSNext",
					"icon_type": "Link",
					"link_type": "Workspace Sidebar",
					"link_to": "POSNext",
					"icon": "shopping-cart",
					"app": "pos_next",
					"standard": 0,
					"hidden": 0,
					"restrict_removal": 0,
					"bg_color": "gray",
				}
			).insert(ignore_permissions=True)
			if not quiet:
				log_message("Created POSNext Desktop Icon linked to pos_next app", level="info")
	except Exception as e:
		log_message(f"Error setting up POSNext desktop icon: {str(e)}", level="error")
		frappe.log_error(title="Desktop Icon Setup Error", message=frappe.get_traceback())


def reclaim_pos_settings_doctype(quiet=False):
	"""Reclaim the `POS Settings` DocType from ERPNext.

	ERPNext ships a Single `POS Settings` (module Accounts) with only
	`invoice_fields` and `pos_search_fields`. POS Next ships its own
	non-Single `POS Settings` (module POS Next) with per-profile config
	and a `barcode_rules` child table. Because ERPNext is in our
	`required_apps` its doctype sync runs after ours during `bench
	migrate`, so its JSON wins on disk unless we re-install our version
	after both apps have finished syncing.

	Runs from `after_migrate`. Idempotent: if the live doctype already
	belongs to POS Next (module == 'POS Next' and not Single), exits
	without touching anything.
	"""
	if not frappe.db.exists("DocType", "POS Settings"):
		if not quiet:
			log_message("POS Settings DocType missing, skipping reclaim", level="warning")
		return

	row = frappe.db.get_value("DocType", "POS Settings", ["module", "issingle"], as_dict=True)
	if row and row.module == "POS Next" and not row.issingle:
		if not quiet:
			log_message("POS Settings already owned by POS Next, nothing to reclaim", level="info")
		return

	if not quiet:
		log_message(
			f"Reclaiming POS Settings DocType (was module={row.module if row else '?'}, "
			f"issingle={row.issingle if row else '?'})",
			level="warning",
		)

	try:
		# Commit any open transaction first — DROP TABLE is DDL and would
		# otherwise trigger ImplicitCommitError under Frappe's safety check.
		frappe.db.commit()
		frappe.db.sql("DROP TABLE IF EXISTS `tabPOS Settings`")
		frappe.db.commit()
		frappe.db.sql("DELETE FROM `tabSingles` WHERE doctype = 'POS Settings'")
		frappe.db.sql("DELETE FROM `tabDocField` WHERE parent = 'POS Settings'")
		frappe.db.sql("DELETE FROM `tabDocPerm` WHERE parent = 'POS Settings'")
		frappe.db.sql("DELETE FROM `tabDocType` WHERE name = 'POS Settings'")
		frappe.db.commit()
		log_message("Dropped legacy POS Settings meta + table", level="info", indent=1)
	except Exception:
		frappe.log_error(
			title="POS Settings Reclaim Error",
			message="Failed to drop legacy POS Settings\n\n" + frappe.get_traceback(),
		)
		raise

	try:
		frappe.reload_doc("pos_next", "doctype", "pos_settings", force=True)
		frappe.reload_doc("pos_next", "doctype", "pos_barcode_rules", force=True)
		frappe.reload_doc("pos_next", "doctype", "pos_allowed_locale", force=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(
			title="POS Settings Reclaim Error",
			message="Failed to reload pos_next doctypes\n\n" + frappe.get_traceback(),
		)
		raise

	after = frappe.db.get_value("DocType", "POS Settings", ["module", "issingle"], as_dict=True)
	if not after or after.module != "POS Next" or after.issingle:
		frappe.log_error(
			title="POS Settings Reclaim Error",
			message=(
				f"Reclaim ran but doctype still wrong: {after}. "
				"ERPNext may be re-importing POS Settings later in the migration."
			),
		)
		log_message(f"Reclaim verification FAILED — doctype is now {after}", level="error")
		return

	if not quiet:
		log_message(
			f"POS Settings reclaimed (module={after.module}, issingle={after.issingle})",
			level="success",
		)
