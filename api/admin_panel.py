"""RackForge admin dashboard — database overview, actions and export."""

from __future__ import annotations

import csv
import hashlib
import html
import hmac
import io
import json
import os
import re
import secrets
import smtplib
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from email_templates import (
    TOKEN_VALID_HOURS,
    admin_reset_code_email_content,
    build_reset_code_message,
    normalize_lang,
)
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, quote, unquote_plus, urlparse

ADMIN_COOKIE = "rackforge_admin"
ADMIN_SESSION_HOURS = 8
ADMIN_PASSWORD = os.environ.get("RACKFORGE_ADMIN_PASSWORD", "").strip()
APP_URL = os.environ.get("RACKFORGE_APP_URL", "https://10.0.40.12").rstrip("/")
AVATAR_DIR = os.environ.get("RACKFORGE_AVATAR_DIR", "/home/stef/rackforge/avatars")
ADMIN_SESSIONS: dict[str, dict[str, Any]] = {}
ADMIN_FLASH: dict[str, str] = {}
ADMIN_LOGIN_PATH = "/admin/login"
ADMIN_PANEL_PATH = "/admin/panel"
ADMIN_USERS_PATH = "/admin/users"
ADMIN_CHANGE_PASSWORD_PATH = "/admin/change-password"
ADMIN_FORGOT_PATH = "/admin/forgot-password"
ADMIN_FORGOT_VERIFY_PATH = "/admin/forgot-password/verify"
ADMIN_RESET_PATH = "/admin/reset-password"
ADMIN_RESET_EMAIL = os.environ.get("RACKFORGE_ADMIN_RESET_EMAIL", "").strip()
SMTP_HOST = os.environ.get("RACKFORGE_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("RACKFORGE_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("RACKFORGE_SMTP_USER", "")
SMTP_PASS = os.environ.get("RACKFORGE_SMTP_PASS", "")
SMTP_FROM = os.environ.get(
    "RACKFORGE_SMTP_FROM", "noreply RackForge <noreply@netwerkengineer.com>"
)
ADMIN_RESET_TOKEN_RE = re.compile(r"^[a-f0-9]{64}$")
ADMIN_RESET_CODE_RE = re.compile(r"^\d{6}$")
ADMIN_USER_ACTIONS = frozenset(
    {
        "create_admin_user",
        "update_admin_role",
        "delete_admin_user",
        "require_admin_password_reset",
    }
)
PBKDF2_ROUNDS = 260_000
ADMIN_ROLES = ("owner", "superadmin", "administrator", "moderator")
ROLE_LABELS = {
    "owner": "Owner",
    "superadmin": "Super Admin",
    "administrator": "Administrator",
    "moderator": "Moderator",
}
ADMIN_I18N: dict[str, dict[str, Any]] = {
    "nl": {
        "language": "Taal",
        "logout": "Uitloggen",
        "login": "Inloggen",
        "account": {
            "changePassword": "Wachtwoord wijzigen",
        },
        "username": "Gebruikersnaam",
        "password": "Wachtwoord",
        "dbManagement": "Databasebeheer",
        "confirmContinue": " — doorgaan?",
        "nav": {
            "dashboard": "Dashboard",
            "adminUsers": "Gebruikers",
            "aria": "Admin navigatie",
        },
        "usersPage": {
            "title": "Gebruikers",
            "subtitle": "Rollen en toegang",
            "search": "Zoeken op gebruikersnaam, e-mail of rol…",
            "addTitle": "Admin-gebruiker toevoegen",
            "email": "E-mail",
            "role": "Rol",
            "add": "Toevoegen",
            "requirePasswordChange": "Nieuw wachtwoord verplicht bij eerste login",
            "passwordChangeRequired": "Wachtwoord wijzigen",
            "save": "Opslaan",
            "delete": "Verwijderen",
            "resetPassword": "Wachtwoord resetten",
            "resetPasswordNew": "Nieuw wachtwoord",
            "colUsername": "Gebruikersnaam",
            "colRole": "Rol",
            "colCreated": "Aangemaakt",
            "colLastLogin": "Laatste login",
            "colActions": "Acties",
            "empty": "Nog geen admin-gebruikers in de database",
            "permissionsTitle": "Rechtenoverzicht",
        },
        "changePassword": {
            "title": "Nieuw wachtwoord instellen",
            "subtitle": "Kies een nieuw wachtwoord om verder te gaan in het panel.",
            "voluntarySubtitle": "Wijzig je panelwachtwoord.",
            "currentPassword": "Huidig wachtwoord",
            "newPassword": "Nieuw wachtwoord",
            "confirmPassword": "Bevestig wachtwoord",
            "save": "Wachtwoord opslaan",
            "back": "Terug naar panel",
            "passwordMismatch": "Wachtwoorden komen niet overeen",
        },
        "dashboard": {
            "title": "RackForge Panel",
            "search": "Zoeken (naam, e-mail, ID…)",
            "exportUsers": "Export gebruikers",
            "exportPlans": "Export racks",
            "exportSessions": "Export sessies",
            "exportAll": "Export alles (JSON)",
            "statsUsers": "Gebruikers",
            "statsNew7d": "Nieuw (7d)",
            "statsNew30d": "Nieuw (30d)",
            "statsActive7d": "Actief (7d)",
            "statsSessions": "Sessies nu",
            "statsPlans": "Rack-plannen",
            "statsGoogle": "Google",
            "statsBlocked": "Geblokkeerd",
            "statsVerify": "Verificaties",
            "statsResets": "Resets",
            "registrations": "Registraties per dag (14 dagen)",
        },
        "roles": ROLE_LABELS,
        "perms": {
            "ownerTitle": "Owner",
            "ownerCreate": "Aanmaken: alle rollen",
            "ownerEdit": "Rollen wijzigen: alle accounts",
            "ownerDelete": "Verwijderen: alle users",
            "superadminTitle": "Super Admin",
            "superadminCreate": "Aanmaken: Administrator en Moderator",
            "superadminEdit": "Rollen wijzigen: Administrator en Moderator",
            "superadminDelete": "Verwijderen: Administrator en Moderator",
            "adminTitle": "Administrator",
            "adminCreate": "Aanmaken: alleen Moderator",
            "adminEdit": "Rollen wijzigen: geen rechten",
            "adminDelete": "Verwijderen: alleen Moderator",
            "moderatorTitle": "Moderator",
            "moderatorNone": "Geen toegang tot admin-gebruikersbeheer",
        },
        "common": {
            "yes": "ja",
            "no": "nee",
            "empty": "leeg",
            "blocked": "geblokkeerd",
            "plans": "{count} plan(s)",
        },
        "actions": {
            "block": "Blokkeren",
            "unblock": "Deblokkeren",
            "delete": "Verwijderen",
            "revoke": "Beëindigen",
            "purgeExpired": "Verlopen opschonen",
            "details": "Details",
        },
        "tables": {
            "usersTitle": "Gebruikers",
            "usersEmpty": "Geen gebruikers",
            "colAvatar": "",
            "colName": "Naam",
            "colEmail": "E-mail",
            "colVerified": "Bevestigd",
            "colLogin": "Login",
            "colPassword": "Ww",
            "colLastLogin": "Laatste login",
            "colRack": "Rack",
            "colCreated": "Aangemaakt",
            "colActions": "Acties",
            "colId": "ID",
            "colLanguage": "Taal",
            "colRackDevices": "Rack",
            "plansTitle": "Rack-plannen",
            "plansEmpty": "Geen rack-plannen",
            "colPlanId": "Plan-ID",
            "colHeight": "Hoogte",
            "colDevices": "Apparaten",
            "colOwner": "Eigenaar",
            "colUpdated": "Bijgewerkt",
            "sessionsTitle": "Actieve sessies",
            "sessionsEmpty": "Geen actieve sessies",
            "colUser": "Gebruiker",
            "colLoggedIn": "Ingelogd",
            "colExpires": "Verloopt",
            "colToken": "Token",
            "verificationsTitle": "Open e-mailverificaties",
            "verificationsEmpty": "Geen open verificaties",
            "colPurpose": "Doel",
            "resetsTitle": "Open wachtwoord-resets",
            "resetsEmpty": "Geen open wachtwoord-resets",
            "colCode": "Code",
            "oauthTitle": "Google OAuth-states",
            "oauthEmpty": "Geen actieve OAuth-states",
            "colState": "State",
            "noRegistrations": "Geen registraties in de laatste 14 dagen.",
            "dbLabel": "DB",
        },
        "login": {
            "title": "Inloggen",
            "wrongCredentials": "Onjuist gebruikersnaam of wachtwoord",
            "notConfigured": "Admin niet geconfigureerd. Voeg een admin-gebruiker toe of zet RACKFORGE_ADMIN_PASSWORD in ~/.config/rackforge/admin.env.",
            "resetSuccess": "Wachtwoord bijgewerkt. Je kunt nu inloggen.",
            "forgotPassword": "Wachtwoord vergeten?",
            "tagline": "Plan. Build. Forge your rack.",
            "secureAccess": "Beveiligde toegang",
            "staffOnly": "Alleen geautoriseerd personeel",
            "controlCenter": "Beheeromgeving",
            "sessionLabel": "Paneelsessie",
            "asideTagline": "Intern beheer van gebruikers, racks en data.",
            "asideSystemStatus": "Systeemstatus",
            "asideStatusService": "Service",
            "asideStatusOnline": "Online",
            "asideStatusAuth": "Authenticatie",
            "asideStatusAuthValue": "Verplicht",
            "asideStatusSession": "Sessie",
            "asideStatusSessionValue": "Versleuteld",
            "asideRolesTitle": "Toegangsniveaus",
            "asideAuditNote": "Alle paneelacties worden gelogd en zijn traceerbaar.",
        },
        "forgotPassword": {
            "title": "Wachtwoord vergeten",
            "subtitle": "Vul je panel-gebruikersnaam in. We sturen een code naar het gekoppelde e-mailadres.",
            "submit": "Resetcode versturen",
            "backToLogin": "Terug naar inloggen",
            "verifyTitle": "Code invoeren",
            "verifySubtitle": "Voer de 6-cijferige code in die we naar {email} hebben gestuurd.",
            "code": "Verificatiecode",
            "verifySubmit": "Code bevestigen",
            "codeSent": "Resetcode verstuurd naar {email}.",
            "resetTitle": "Nieuw wachtwoord",
            "resetSubtitle": "Kies een nieuw wachtwoord voor het panel.",
            "resetSubmit": "Wachtwoord opslaan",
        },
        "flash": {
            "noAdminRights": "Geen rechten om admin-gebruikers te beheren",
            "noPermission": "Geen rechten voor deze actie",
            "invalidUsername": "Gebruikersnaam: 3–32 tekens, letters/cijfers/underscore",
            "emailRequired": "E-mail is verplicht",
            "invalidEmail": "Ongeldig e-mailadres",
            "emailExists": "E-mailadres is al in gebruik",
            "passwordRequired": "Wachtwoord is verplicht",
            "wrongCurrentPassword": "Huidig wachtwoord is onjuist",
            "passwordUpdated": "Wachtwoord bijgewerkt",
            "forgotUserNotFound": "Gebruikersnaam niet gevonden",
            "noResetEmail": "Geen e-mailadres gekoppeld aan dit panel-account",
            "smtpNotConfigured": "E-mail is niet geconfigureerd — reset niet mogelijk",
            "resetEmailFailed": "Kon resetmail niet versturen",
            "invalidResetCode": "Ongeldige of verlopen code",
            "invalidResetToken": "Ongeldige of verlopen resetlink",
            "resetPasswordUpdated": "Panelwachtwoord bijgewerkt",
            "invalidRole": "Ongeldige rol",
            "usernameExists": "Gebruikersnaam bestaat al",
            "onlyOwnerSuperChangeRoles": "Alleen Owner en Super Admin kunnen rollen wijzigen",
            "invalidAdminId": "Ongeldig admin-ID",
            "adminNotFound": "Admin-gebruiker niet gevonden",
            "noEditAdminRights": "Geen rechten om deze admin-gebruiker te wijzigen",
            "cannotDemoteLastOwner": "Kan de laatste Owner niet degraderen",
            "cannotDemoteLastSuperadmin": "Kan de laatste superbeheerder niet degraderen",
            "cannotDeleteSelf": "Je kunt jezelf niet verwijderen",
            "cannotResetSelfPassword": "Je kunt je eigen wachtwoord niet op deze manier resetten",
            "noResetPasswordRights": "Geen rechten om het wachtwoord van deze gebruiker te resetten",
            "noDeleteAdminRights": "Geen rechten om deze admin-gebruiker te verwijderen",
            "cannotDeleteLastOwner": "Kan de laatste Owner niet verwijderen",
            "cannotDeleteLastSuperadmin": "Kan de laatste superbeheerder niet verwijderen",
            "adminDeleted": "Admin-gebruiker verwijderd",
            "adminAdded": "Admin {username} toegevoegd als {role}",
            "passwordResetRequired": "Wachtwoord van {username} ingesteld — bij volgende login nieuw wachtwoord verplicht",
            "roleUpdated": "Rol bijgewerkt naar {role}",
            "onlyOwnerAssign": "Alleen een Owner kan de rol Owner toekennen",
            "superadminRoleLimit": "Super Admin kan alleen Administrator en Moderator toekennen",
            "adminOnlyModerator": "Administrator kan alleen Moderator aanmaken",
            "noRolePermission": "Geen rechten om deze rol toe te kennen",
            "invalidUserId": "Ongeldig gebruiker-ID",
            "userDeleted": "Gebruiker verwijderd",
            "userNotFound": "Gebruiker niet gevonden",
            "userUnblocked": "Gebruiker gedeblokkeerd",
            "userBlocked": "Gebruiker geblokkeerd",
            "invalidSession": "Ongeldige sessie",
            "sessionRevoked": "Sessie beëindigd",
            "invalidPlanId": "Ongeldig plan-ID",
            "planDeleted": "Rack-plan verwijderd",
            "purged": "Verlopen records opgeschoond",
            "unknownAction": "Onbekende actie",
        },
    },
    "en": {
        "language": "Language",
        "logout": "Log out",
        "login": "Log in",
        "account": {
            "changePassword": "Change password",
        },
        "username": "Username",
        "password": "Password",
        "dbManagement": "Database management",
        "confirmContinue": " — continue?",
        "nav": {
            "dashboard": "Dashboard",
            "adminUsers": "Users",
            "aria": "Admin navigation",
        },
        "usersPage": {
            "title": "Users",
            "subtitle": "Roles and access",
            "search": "Search by username, email or role…",
            "addTitle": "Add admin user",
            "email": "Email",
            "role": "Role",
            "add": "Add",
            "requirePasswordChange": "Require new password on first login",
            "passwordChangeRequired": "Password change",
            "save": "Save",
            "delete": "Delete",
            "resetPassword": "Reset password",
            "resetPasswordNew": "New password",
            "colUsername": "Username",
            "colRole": "Role",
            "colCreated": "Created",
            "colLastLogin": "Last login",
            "colActions": "Actions",
            "empty": "No admin users in the database yet",
            "permissionsTitle": "Permissions overview",
        },
        "changePassword": {
            "title": "Set new password",
            "subtitle": "Choose a new password to continue in the panel.",
            "voluntarySubtitle": "Change your panel password.",
            "currentPassword": "Current password",
            "newPassword": "New password",
            "confirmPassword": "Confirm password",
            "save": "Save password",
            "back": "Back to panel",
            "passwordMismatch": "Passwords do not match",
        },
        "dashboard": {
            "title": "RackForge Panel",
            "search": "Search (name, email, ID…)",
            "exportUsers": "Export users",
            "exportPlans": "Export racks",
            "exportSessions": "Export sessions",
            "exportAll": "Export all (JSON)",
            "statsUsers": "Users",
            "statsNew7d": "New (7d)",
            "statsNew30d": "New (30d)",
            "statsActive7d": "Active (7d)",
            "statsSessions": "Sessions now",
            "statsPlans": "Rack plans",
            "statsGoogle": "Google",
            "statsBlocked": "Blocked",
            "statsVerify": "Verifications",
            "statsResets": "Resets",
            "registrations": "Registrations per day (14 days)",
        },
        "roles": {
            "owner": "Owner",
            "superadmin": "Super Admin",
            "administrator": "Administrator",
            "moderator": "Moderator",
        },
        "perms": {
            "ownerTitle": "Owner",
            "ownerCreate": "Create: all roles",
            "ownerEdit": "Change roles: all accounts",
            "ownerDelete": "Delete: all users",
            "superadminTitle": "Super Admin",
            "superadminCreate": "Create: Administrator and Moderator",
            "superadminEdit": "Change roles: Administrator and Moderator",
            "superadminDelete": "Delete: Administrator and Moderator",
            "adminTitle": "Administrator",
            "adminCreate": "Create: Moderator only",
            "adminEdit": "Change roles: no permission",
            "adminDelete": "Delete: Moderator only",
            "moderatorTitle": "Moderator",
            "moderatorNone": "No access to admin user management",
        },
        "common": {
            "yes": "yes",
            "no": "no",
            "empty": "empty",
            "blocked": "blocked",
            "plans": "{count} plan(s)",
        },
        "actions": {
            "block": "Block",
            "unblock": "Unblock",
            "delete": "Delete",
            "revoke": "Revoke",
            "purgeExpired": "Purge expired",
            "details": "Details",
        },
        "tables": {
            "usersTitle": "Users",
            "usersEmpty": "No users",
            "colAvatar": "",
            "colName": "Name",
            "colEmail": "Email",
            "colVerified": "Verified",
            "colLogin": "Login",
            "colPassword": "Pwd",
            "colLastLogin": "Last login",
            "colRack": "Rack",
            "colCreated": "Created",
            "colActions": "Actions",
            "colId": "ID",
            "colLanguage": "Language",
            "colRackDevices": "Rack",
            "plansTitle": "Rack plans",
            "plansEmpty": "No rack plans",
            "colPlanId": "Plan ID",
            "colHeight": "Height",
            "colDevices": "Devices",
            "colOwner": "Owner",
            "colUpdated": "Updated",
            "sessionsTitle": "Active sessions",
            "sessionsEmpty": "No active sessions",
            "colUser": "User",
            "colLoggedIn": "Signed in",
            "colExpires": "Expires",
            "colToken": "Token",
            "verificationsTitle": "Open email verifications",
            "verificationsEmpty": "No open verifications",
            "colPurpose": "Purpose",
            "resetsTitle": "Open password resets",
            "resetsEmpty": "No open password resets",
            "colCode": "Code",
            "oauthTitle": "Google OAuth states",
            "oauthEmpty": "No active OAuth states",
            "colState": "State",
            "noRegistrations": "No registrations in the last 14 days.",
            "dbLabel": "DB",
        },
        "login": {
            "title": "Log in",
            "wrongCredentials": "Incorrect username or password",
            "notConfigured": "Admin is not configured. Add an admin user or set RACKFORGE_ADMIN_PASSWORD in ~/.config/rackforge/admin.env.",
            "resetSuccess": "Password updated. You can log in now.",
            "forgotPassword": "Forgot password?",
            "tagline": "Plan. Build. Forge your rack.",
            "secureAccess": "Secure access",
            "staffOnly": "Authorized personnel only",
            "controlCenter": "Control environment",
            "sessionLabel": "Panel session",
            "asideTagline": "Internal management of users, racks and data.",
            "asideSystemStatus": "System status",
            "asideStatusService": "Service",
            "asideStatusOnline": "Online",
            "asideStatusAuth": "Authentication",
            "asideStatusAuthValue": "Required",
            "asideStatusSession": "Session",
            "asideStatusSessionValue": "Encrypted",
            "asideRolesTitle": "Access levels",
            "asideAuditNote": "All panel actions are logged and traceable.",
        },
        "forgotPassword": {
            "title": "Forgot password",
            "subtitle": "Enter your panel username. We'll send a code to the linked email address.",
            "submit": "Send reset code",
            "backToLogin": "Back to login",
            "verifyTitle": "Enter code",
            "verifySubtitle": "Enter the 6-digit code we sent to {email}.",
            "code": "Verification code",
            "verifySubmit": "Confirm code",
            "codeSent": "Reset code sent to {email}.",
            "resetTitle": "New password",
            "resetSubtitle": "Choose a new password for the panel.",
            "resetSubmit": "Save password",
        },
        "flash": {
            "noAdminRights": "No permission to manage admin users",
            "noPermission": "No permission for this action",
            "invalidUsername": "Username: 3–32 characters, letters/numbers/underscore",
            "emailRequired": "Email is required",
            "invalidEmail": "Invalid email address",
            "emailExists": "Email address is already in use",
            "passwordRequired": "Password is required",
            "wrongCurrentPassword": "Current password is incorrect",
            "passwordUpdated": "Password updated",
            "forgotUserNotFound": "Username not found",
            "noResetEmail": "No email address linked to this panel account",
            "smtpNotConfigured": "Email is not configured — reset unavailable",
            "resetEmailFailed": "Could not send reset email",
            "invalidResetCode": "Invalid or expired code",
            "invalidResetToken": "Invalid or expired reset link",
            "resetPasswordUpdated": "Panel password updated",
            "invalidRole": "Invalid role",
            "usernameExists": "Username already exists",
            "onlyOwnerSuperChangeRoles": "Only Owner and Super Admin can change roles",
            "invalidAdminId": "Invalid admin ID",
            "adminNotFound": "Admin user not found",
            "noEditAdminRights": "No permission to edit this admin user",
            "cannotDemoteLastOwner": "Cannot demote the last Owner",
            "cannotDemoteLastSuperadmin": "Cannot demote the last super admin",
            "cannotDeleteSelf": "You cannot delete yourself",
            "cannotResetSelfPassword": "You cannot reset your own password this way",
            "noResetPasswordRights": "No permission to reset this user's password",
            "noDeleteAdminRights": "No permission to delete this admin user",
            "cannotDeleteLastOwner": "Cannot delete the last Owner",
            "cannotDeleteLastSuperadmin": "Cannot delete the last super admin",
            "adminDeleted": "Admin user deleted",
            "adminAdded": "Admin {username} added as {role}",
            "passwordResetRequired": "Password set for {username} — new password required on next login",
            "roleUpdated": "Role updated to {role}",
            "onlyOwnerAssign": "Only an Owner can assign the Owner role",
            "superadminRoleLimit": "Super Admin can only assign Administrator and Moderator",
            "adminOnlyModerator": "Administrator can only create Moderator",
            "noRolePermission": "No permission to assign this role",
            "invalidUserId": "Invalid user ID",
            "userDeleted": "User deleted",
            "userNotFound": "User not found",
            "userUnblocked": "User unblocked",
            "userBlocked": "User blocked",
            "invalidSession": "Invalid session",
            "sessionRevoked": "Session revoked",
            "invalidPlanId": "Invalid plan ID",
            "planDeleted": "Rack plan deleted",
            "purged": "Expired records purged",
            "unknownAction": "Unknown action",
        },
    },
}
LEGACY_ADMIN_ROLES = {
    "admin": "administrator",
    "beheerder": "administrator",
    "alleen_lezen": "moderator",
    "read": "moderator",
    "readonly": "moderator",
    "viewer": "moderator",
}
ID_RE = re.compile(r"^[a-f0-9]{32}$")
ADMIN_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
ADMIN_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

BASE_STYLE = """
:root {
  --bg: #0a0f14; --surface: #111a22; --surface-2: #162029; --border: #1e2d3a;
  --text: #e8f0f7; --muted: #7a92a8; --accent: #1bdb7a; --danger: #ef4444;
  --mono: "JetBrains Mono", ui-monospace, monospace;
  --font: "DM Sans", system-ui, sans-serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font); background: var(--bg); color: var(--text); min-height: 100vh; line-height: 1.5; }
.wrap { max-width: 1400px; margin: 0 auto; padding: 2rem 1.25rem 3rem; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; }
h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
.sub { color: var(--muted); font-size: 0.9rem; margin-bottom: 1rem; }
label { display: block; font-size: 0.8rem; color: var(--muted); margin-bottom: 0.35rem; }
input[type=text], input[type=email], input[type=password], input[type=search], select {
  width: 100%; background: var(--surface-2); border: 1px solid var(--border);
  color: var(--text); padding: 0.65rem 0.75rem; border-radius: 8px; font: inherit;
}
.inline-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.65rem; align-items: end; margin-bottom: 1rem; }
.inline-form .btn { width: 100%; }
input:focus { outline: none; border-color: var(--accent); }
.btn {
  display: inline-block; border: none; border-radius: 8px; padding: 0.45rem 0.75rem;
  font: inherit; font-size: 0.78rem; font-weight: 600; cursor: pointer; text-decoration: none;
}
.btn--primary { background: var(--accent); color: #04140c; }
.btn--ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); }
.btn--danger { background: rgba(239,68,68,.15); color: var(--danger); border: 1px solid rgba(239,68,68,.35); }
.btn--sm { padding: 0.3rem 0.55rem; font-size: 0.72rem; }
.err { color: var(--danger); font-size: 0.85rem; margin-top: 0.75rem; }
.ok { color: var(--accent); font-size: 0.85rem; margin-bottom: 1rem; }
.topbar { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; margin-bottom: 1.25rem; flex-wrap: wrap; }
.admin-nav { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }
.admin-nav a { text-decoration: none; }
.admin-nav a[aria-current="page"] { border-color: var(--accent); color: var(--accent); }
.toolbar { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; margin-bottom: 1.25rem; }
.toolbar input[type=search] { max-width: 280px; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 0.65rem; margin-bottom: 1.25rem; }
.stat { background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px; padding: 0.75rem 0.9rem; }
.stat__n { font-size: 1.25rem; font-weight: 700; }
.stat__l { color: var(--muted); font-size: 0.72rem; }
section { margin-top: 1.35rem; }
section h2 { font-size: 0.95rem; margin-bottom: 0.65rem; color: var(--muted); font-weight: 600; }
.table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 10px; }
table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
th, td { padding: 0.5rem 0.65rem; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
th { background: var(--surface-2); color: var(--muted); font-weight: 600; white-space: nowrap; }
tr:last-child td { border-bottom: none; }
.mono { font-family: var(--mono); font-size: 0.75rem; }
.pill { display: inline-block; padding: 0.1rem 0.45rem; border-radius: 999px; font-size: 0.7rem; border: 1px solid var(--border); }
.pill--ok { color: var(--accent); border-color: rgba(27,219,122,.35); }
.pill--warn { color: #f59e0b; border-color: rgba(245,158,11,.35); }
.pill--danger { color: var(--danger); border-color: rgba(239,68,68,.35); }
.avatar { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; background: var(--surface-2); border: 1px solid var(--border); }
.avatar--empty { display: inline-block; }
.actions { display: flex; gap: 0.35rem; flex-wrap: wrap; align-items: center; }
.admin-reset-form { display: flex; gap: 0.35rem; flex-wrap: wrap; align-items: center; }
.admin-reset-form input[type=password] { width: auto; min-width: 7.5rem; max-width: 10rem; padding: 0.3rem 0.5rem; font-size: 0.72rem; }
details.user-detail { margin-top: 0.35rem; font-size: 0.75rem; color: var(--muted); }
details.user-detail summary { cursor: pointer; color: var(--accent); }
.week-bars { display: flex; flex-direction: column; gap: 0.35rem; }
.week-bar { display: flex; align-items: center; gap: 0.5rem; font-size: 0.78rem; }
.week-bar__track { flex: 1; height: 8px; background: var(--surface-2); border-radius: 4px; overflow: hidden; }
.week-bar__fill { height: 100%; background: var(--accent); border-radius: 4px; }
[hidden] { display: none !important; }
.role-perms { margin-top: 0.75rem; display: flex; flex-direction: column; gap: 0.55rem; }
.role-perms__item { background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 0.65rem 0.85rem; }
.role-perms__title { font-size: 0.82rem; font-weight: 600; color: var(--text); margin-bottom: 0.3rem; }
.role-perms__list { margin: 0; padding-left: 1.1rem; font-size: 0.82rem; }
.role-perms__list li { margin: 0.15rem 0; }
.topbar__actions { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.admin-lang { display: flex; align-items: center; gap: 0.35rem; font-size: 0.78rem; color: var(--muted); }
.admin-lang select { width: auto; min-width: 4.2rem; padding: 0.35rem 0.5rem; font-size: 0.78rem; }
.login-top { display: flex; justify-content: flex-end; margin-bottom: 0.75rem; }
.sub a { color: var(--accent); text-decoration: none; }
.sub a:hover { text-decoration: underline; }
body.admin-auth {
  min-height: 100vh;
  background: #070b10;
  position: relative;
  overflow-x: hidden;
}
body.admin-auth .admin-auth__wrap {
  max-width: none;
  min-height: 100vh;
  padding: 0;
  position: relative;
  z-index: 1;
}
.admin-auth__bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
  background:
    radial-gradient(ellipse 45% 40% at 22% 45%, rgba(27, 219, 122, 0.09) 0%, transparent 70%),
    radial-gradient(ellipse 40% 35% at 78% 50%, rgba(59, 130, 246, 0.06) 0%, transparent 65%),
    radial-gradient(ellipse 50% 35% at 50% 100%, rgba(27, 219, 122, 0.05) 0%, transparent 60%),
    linear-gradient(180deg, #060a0f 0%, #0a1018 45%, #070b10 100%);
}
.admin-auth__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(122, 146, 168, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(122, 146, 168, 0.05) 1px, transparent 1px);
  background-size: 24px 24px;
  mask-image: linear-gradient(180deg, #000 0%, #000 55%, transparent 100%);
}
.admin-auth__scanline {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(255, 255, 255, 0.012) 2px,
    rgba(255, 255, 255, 0.012) 3px
  );
  opacity: 0.35;
}
.admin-auth__gate { position: relative; width: 100%; min-height: 100vh; }
.admin-auth__layout {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: 1fr min(400px, 38vw);
  width: 100%;
  min-height: 100vh;
}
.admin-auth__showcase {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
  padding: 2rem 3vw;
}
.admin-auth__showcase-brand {
  display: flex;
  align-items: center;
  gap: 1.15rem;
  max-width: min(520px, 90vw);
}
.admin-auth__logo {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 72px;
  height: 72px;
  border-radius: 16px;
  background: linear-gradient(145deg, #141f29 0%, #0d141c 100%);
  border: 1px solid rgba(27, 219, 122, 0.45);
  box-shadow:
    0 0 0 1px rgba(27, 219, 122, 0.12),
    0 0 28px rgba(27, 219, 122, 0.22);
  color: #c5d4e3;
  overflow: hidden;
}
.admin-auth__logo-svg {
  width: 44px;
  height: 44px;
  display: block;
}
.admin-auth__showcase-text {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}
.admin-auth__showcase-title {
  font-size: clamp(1.65rem, 4vw, 2.35rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--text);
}
.admin-auth__showcase-title span { color: var(--accent); }
.admin-auth__showcase-sub {
  font-size: 0.72rem;
  font-family: var(--mono);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
}
.admin-auth__showcase-tagline {
  margin: 0.15rem 0 0;
  font-size: 0.92rem;
  line-height: 1.5;
  color: var(--muted);
  max-width: 26rem;
}
.admin-auth__panel {
  max-width: none;
  width: 100%;
  margin: 0;
  border-radius: 0;
  align-self: stretch;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0;
  z-index: 2;
  backdrop-filter: blur(14px);
  background: rgba(12, 18, 24, 0.9);
  border-left: 1px solid rgba(27, 219, 122, 0.22);
  box-shadow:
    -12px 0 40px rgba(0, 0, 0, 0.35),
    inset 1px 0 0 rgba(27, 219, 122, 0.08);
}
.admin-auth__panel-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.7rem 1.25rem;
  background: rgba(8, 14, 20, 0.95);
  border-bottom: 1px solid var(--border);
  font-size: 0.68rem;
  font-family: var(--mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.admin-auth__panel-status {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}
.admin-auth__status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px rgba(27, 219, 122, 0.65);
}
.admin-auth__panel-body {
  padding: 2rem 2.25rem 2.25rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  flex: 1;
}
.admin-auth__panel-head {
  margin-bottom: 1.35rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(30, 45, 58, 0.85);
}
.admin-auth__panel-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.55rem;
}
.admin-auth__session-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(27, 219, 122, 0.28);
  background: rgba(27, 219, 122, 0.08);
  font-size: 0.62rem;
  font-family: var(--mono);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--accent);
}
.admin-auth__session-badge::before {
  content: "";
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 6px rgba(27, 219, 122, 0.6);
}
.admin-auth__title {
  font-size: 1.3rem;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.02em;
}
.admin-auth__subtitle {
  margin: 0.35rem 0 0;
  font-size: 0.82rem;
  color: var(--muted);
  font-family: var(--mono);
  letter-spacing: 0.03em;
}
.admin-auth__form {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.admin-auth__form label {
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: #6b8499;
  margin-top: 0.65rem;
}
.admin-auth__form label:first-of-type { margin-top: 0; }
.admin-auth__form input {
  background: rgba(8, 13, 18, 0.95);
  border-color: rgba(36, 52, 68, 0.95);
  font-family: var(--mono);
  font-size: 0.88rem;
  padding: 0.72rem 0.8rem;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.admin-auth__form input:focus {
  border-color: rgba(27, 219, 122, 0.55);
  box-shadow: 0 0 0 3px rgba(27, 219, 122, 0.12);
}
.admin-auth__form .btn--primary {
  margin-top: 1.1rem;
  width: 100%;
  padding: 0.72rem 1rem;
  font-family: var(--mono);
  font-size: 0.82rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  box-shadow: 0 0 20px rgba(27, 219, 122, 0.18);
}
.admin-auth__form .btn--primary:hover:not(:disabled) {
  box-shadow: 0 0 28px rgba(27, 219, 122, 0.28);
}
.admin-auth__form .btn--ghost,
.admin-auth__panel-body > .btn--ghost {
  margin-top: 0.75rem;
  width: 100%;
  text-align: center;
  font-family: var(--mono);
  font-size: 0.74rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.admin-auth__forgot {
  margin: 0.9rem 0 0;
  text-align: center;
  font-size: 0.78rem;
}
.admin-auth__forgot a {
  color: var(--accent);
  text-decoration: none;
  font-family: var(--mono);
  letter-spacing: 0.03em;
}
.admin-auth__forgot a:hover { text-decoration: underline; }
.admin-auth__panel .err,
.admin-auth__panel .ok {
  margin-top: 0.85rem;
  padding: 0.55rem 0.7rem;
  border-radius: 8px;
  font-family: var(--mono);
  font-size: 0.78rem;
}
.admin-auth__panel .err {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.28);
}
.admin-auth__panel .ok {
  background: rgba(27, 219, 122, 0.1);
  border: 1px solid rgba(27, 219, 122, 0.28);
}
.admin-auth__footer {
  margin-top: 1.35rem;
  padding-top: 0.9rem;
  border-top: 1px dashed rgba(36, 52, 68, 0.95);
  font-size: 0.65rem;
  font-family: var(--mono);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #5f7386;
  text-align: center;
}
.admin-auth__panel-bar .admin-lang { margin: 0; font-size: 0.72rem; }
.admin-auth__panel-bar .admin-lang span { display: none; }
@media (max-width: 900px) {
  .admin-auth__layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }
  .admin-auth__showcase {
    padding: 2rem 1.5rem 1rem;
    gap: 1rem;
  }
  .admin-auth__showcase-brand {
    flex-direction: column;
    text-align: center;
    gap: 1rem;
  }
  .admin-auth__panel {
    border-left: none;
    border-top: 1px solid rgba(27, 219, 122, 0.18);
    box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.25);
  }
  .admin-auth__panel-body { padding: 2rem 1.5rem 2.5rem; }
}
"""

ADMIN_AUTH_BACKGROUND = """
<div class="admin-auth__bg" aria-hidden="true">
  <div class="admin-auth__grid"></div>
  <div class="admin-auth__scanline"></div>
</div>"""

ADMIN_AUTH_LOGO_SVG = """
<svg class="admin-auth__logo-svg" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="3" y="3" width="34" height="34" rx="9" fill="#0a1018" stroke="#243444" stroke-width="1"/>
  <path d="M20 9l10 4.2v7.2c0 5.8-4 10.9-10 12.2-6-1.3-10-6.4-10-12.2v-7.2L20 9z"
    stroke="#1bdb7a" stroke-width="1.15" fill="rgba(27,219,122,0.07)"/>
  <rect x="14.5" y="19.5" width="11" height="8" rx="1.2" stroke="#7a92a8" stroke-width="1"/>
  <path d="M16 22.5h8M16 25h5.5" stroke="#1bdb7a" stroke-width="1.15" stroke-linecap="round"/>
  <circle cx="20" cy="15.2" r="1.35" fill="#1bdb7a"/>
  <path d="M18.8 15.2h2.4M20 13.9v2.6" stroke="#0a1018" stroke-width="0.7" stroke-linecap="round"/>
</svg>"""

ADMIN_I18N_BOOT = """
const ADMIN_LANG_KEY = 'rackforge-lang';
const ADMIN_MESSAGES = __ADMIN_MESSAGES__;
let adminLang = 'nl';

function adminFlashVars(el) {
  const vars = {};
  for (const [key, value] of Object.entries(el.dataset)) {
    if (!key.startsWith('i18nVar')) continue;
    const name = key.slice(7, 8).toLowerCase() + key.slice(8);
    vars[name] = value;
  }
  if (vars.roleKey) vars.role = adminT('roles.' + vars.roleKey);
  return vars;
}

function adminT(key, vars = {}) {
  const parts = key.split('.');
  let value = ADMIN_MESSAGES[adminLang];
  for (const part of parts) {
    value = value?.[part];
  }
  if (typeof value !== 'string') return key;
  return Object.entries(vars).reduce(
    (text, [name, val]) => text.replaceAll('{' + name + '}', val),
    value
  );
}

function applyAdminI18n() {
  document.querySelectorAll('[data-i18n-admin]').forEach((el) => {
    const attr = el.dataset.i18nAdminAttr;
    const value = adminT(el.dataset.i18nAdmin, adminFlashVars(el));
    if (attr) el[attr] = value;
    else el.textContent = value;
  });
  document.querySelectorAll('option[data-i18n-admin]').forEach((opt) => {
    opt.textContent = adminT(opt.dataset.i18nAdmin);
  });
  document.querySelectorAll('.admin-role-pill[data-admin-role]').forEach((el) => {
    el.textContent = adminT('roles.' + el.dataset.adminRole);
  });
  document.documentElement.lang = adminLang;
  const sel = document.getElementById('admin-lang-select');
  if (sel) sel.value = adminLang;
  const pageTitle = document.querySelector('[data-admin-page-title]');
  if (pageTitle) {
    document.title = adminT(pageTitle.dataset.adminPageTitle) + ' — RackForge Panel';
  }
}

function confirmAdminAction(key) {
  return confirm(adminT(key) + adminT('confirmContinue'));
}

function initAdminI18n() {
  const saved = localStorage.getItem(ADMIN_LANG_KEY);
  const browserLang = navigator.language?.toLowerCase().startsWith('nl') ? 'nl' : 'en';
  adminLang = ADMIN_MESSAGES[saved] ? saved : browserLang;
  applyAdminI18n();
  document.getElementById('admin-lang-select')?.addEventListener('change', (e) => {
    adminLang = e.target.value;
    localStorage.setItem(ADMIN_LANG_KEY, adminLang);
    applyAdminI18n();
    document.dispatchEvent(new CustomEvent('adminlangchange'));
  });
}

document.addEventListener('DOMContentLoaded', initAdminI18n);
"""

ADMIN_JS = """
function syncRoleSaveButtons() {
  document.querySelectorAll('.admin-role-form').forEach((form) => {
    const select = form.querySelector('.admin-role-select');
    const btn = form.querySelector('.admin-role-save');
    if (!select || !btn) return;
    const changed = select.value !== select.dataset.initial;
    btn.hidden = !changed;
    btn.disabled = !changed;
  });
}

document.getElementById('admin-search')?.addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase();
  document.querySelectorAll('[data-search]').forEach((row) => {
    row.hidden = q.length > 0 && !row.dataset.search.includes(q);
  });
});

document.querySelectorAll('.admin-role-select').forEach((select) => {
  select.addEventListener('change', syncRoleSaveButtons);
});
document.addEventListener('DOMContentLoaded', syncRoleSaveButtons);
document.addEventListener('adminlangchange', syncRoleSaveButtons);
"""


def admin_configured() -> bool:
    return bool(ADMIN_PASSWORD)


def ensure_admin_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'administrator',
            created_at TEXT NOT NULL,
            last_login TEXT,
            app_user_id TEXT
        )
        """
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(admin_users)")}
    if "app_user_id" not in cols:
        conn.execute("ALTER TABLE admin_users ADD COLUMN app_user_id TEXT")
    if "must_change_password" not in cols:
        conn.execute(
            "ALTER TABLE admin_users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"
        )
    if "email" not in cols:
        conn.execute("ALTER TABLE admin_users ADD COLUMN email TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_password_resets (
            token TEXT PRIMARY KEY,
            admin_id TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "UPDATE admin_users SET role = 'administrator' WHERE role IN ('admin', 'beheerder')"
    )
    conn.execute(
        "UPDATE admin_users SET role = 'moderator' WHERE role IN ('viewer', 'alleen_lezen', 'read', 'readonly')"
    )
    conn.commit()


def upsert_bootstrap_admin(conn: sqlite3.Connection) -> str | None:
    if not admin_configured():
        return None
    row = conn.execute(
        "SELECT id, app_user_id FROM admin_users WHERE username = 'admin' COLLATE NOCASE"
    ).fetchone()
    app_user = conn.execute(
        "SELECT id FROM users WHERE username = 'admin' COLLATE NOCASE"
    ).fetchone()
    app_user_id = app_user["id"] if app_user else None
    if row:
        conn.execute(
            "UPDATE admin_users SET role = 'owner', last_login = ? WHERE id = ?",
            (utc_now_iso(), row["id"]),
        )
        if app_user_id and not row["app_user_id"]:
            conn.execute(
                "UPDATE admin_users SET app_user_id = ? WHERE id = ?",
                (app_user_id, row["id"]),
            )
        conn.commit()
        return row["id"]
    salt, digest = hash_admin_password(ADMIN_PASSWORD)
    admin_id = secrets.token_hex(16)
    conn.execute(
        """
        INSERT INTO admin_users (
            id, username, password_salt, password_hash, role, created_at, last_login, app_user_id
        )
        VALUES (?, 'admin', ?, ?, 'owner', ?, ?, ?)
        """,
        (admin_id, salt, digest, utc_now_iso(), utc_now_iso(), app_user_id),
    )
    conn.commit()
    return admin_id


def sync_env_admin_session(
    conn: sqlite3.Connection, session: dict[str, Any]
) -> dict[str, Any]:
    if session.get("admin_id"):
        return session
    username = str(session.get("username", "")).lower()
    if username not in ("admin", "omgeving"):
        return session
    if normalize_session_role(session.get("role", "")) not in ("owner", "superadmin"):
        return session
    admin_id = upsert_bootstrap_admin(conn)
    if admin_id:
        session["admin_id"] = admin_id
        if username == "omgeving":
            session["username"] = "admin"
    return session


def admin_login_available(conn: sqlite3.Connection) -> bool:
    ensure_admin_schema(conn)
    if admin_configured():
        return True
    return conn.execute("SELECT 1 FROM admin_users LIMIT 1").fetchone() is not None


def hash_admin_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    ).hex()
    return salt, digest


def verify_admin_password_hash(password: str, salt: str, digest: str) -> bool:
    check = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    ).hex()
    return secrets.compare_digest(check, digest)


def verify_env_admin_password(password: str) -> bool:
    if not admin_configured():
        return False
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    expected = hashlib.sha256(ADMIN_PASSWORD.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, expected)


def smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def admin_reset_expires() -> str:
    return (
        datetime.now(timezone.utc) + timedelta(hours=TOKEN_VALID_HOURS)
    ).replace(microsecond=0).isoformat()


def normalize_admin_reset_code(raw: str) -> str:
    return re.sub(r"\D", "", str(raw).strip())


def mask_email(email: str) -> str:
    local, sep, domain = email.partition("@")
    if not sep:
        return email
    if len(local) <= 1:
        masked_local = "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 1)
    return f"{masked_local}@{domain}"


def purge_expired_admin_password_resets(conn: sqlite3.Connection) -> None:
    conn.execute(
        "DELETE FROM admin_password_resets WHERE expires_at < ?", (utc_now_iso(),)
    )


def resolve_admin_reset_email(
    conn: sqlite3.Connection, admin_id: str, username: str
) -> tuple[str, str] | None:
    row = conn.execute(
        """
        SELECT a.email AS admin_email, u.email AS user_email, u.lang AS user_lang
        FROM admin_users a
        LEFT JOIN users u ON u.id = a.app_user_id
        WHERE a.id = ?
        """,
        (admin_id,),
    ).fetchone()
    if not row:
        return None
    email = (row["admin_email"] or row["user_email"] or "").strip()
    if email:
        lang = normalize_lang(row["user_lang"] if row["user_lang"] else "nl")
        return email, lang
    if ADMIN_RESET_EMAIL and username.lower() in ("admin", "owner"):
        return ADMIN_RESET_EMAIL, "nl"
    return None


def create_admin_password_reset(
    conn: sqlite3.Connection, admin_id: str
) -> tuple[str, str]:
    purge_expired_admin_password_resets(conn)
    conn.execute(
        "DELETE FROM admin_password_resets WHERE admin_id = ?", (admin_id,)
    )
    token = secrets.token_hex(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO admin_password_resets (token, admin_id, code, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (token, admin_id, code, admin_reset_expires(), now),
    )
    return token, code


def send_admin_password_reset_email(to_email: str, code: str, lang: str) -> None:
    if not smtp_configured():
        print(
            f"[{utc_now_iso()}] SMTP not configured. Admin reset code for {to_email}: {code}"
        )
        return
    content = admin_reset_code_email_content(lang, code)
    msg = build_reset_code_message(
        to_email=to_email,
        from_addr=SMTP_FROM,
        content=content,
        app_url=APP_URL,
    )
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        if SMTP_PORT == 587:
            smtp.starttls()
            smtp.ehlo()
        if SMTP_USER:
            smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


def verify_session_admin_password(
    conn: sqlite3.Connection, session: dict[str, Any], password: str
) -> bool:
    if not password:
        return False
    admin_id = session.get("admin_id")
    if admin_id:
        row = conn.execute(
            "SELECT password_salt, password_hash FROM admin_users WHERE id = ?",
            (admin_id,),
        ).fetchone()
        if row:
            return verify_admin_password_hash(
                password, row["password_salt"], row["password_hash"]
            )
    return verify_env_admin_password(password)


def role_label(role: str) -> str:
    role = normalize_admin_role(role) or role
    return ROLE_LABELS.get(role, role)


def normalize_admin_role(role: str) -> str | None:
    role = (role or "").strip().lower()
    role = LEGACY_ADMIN_ROLES.get(role, role)
    return role if role in ADMIN_ROLES else None


def normalize_session_role(role: str) -> str:
    return normalize_admin_role(role) or role


def purge_admin_sessions() -> None:
    now = time.time()
    for token, session in list(ADMIN_SESSIONS.items()):
        expires = session.get("expires", 0) if isinstance(session, dict) else session
        if expires <= now:
            ADMIN_SESSIONS.pop(token, None)
            ADMIN_FLASH.pop(token, None)


def admin_redirect(handler: BaseHTTPRequestHandler, location: str) -> None:
    handler.send_response(302)
    handler.send_header("Location", location)
    handler.end_headers()


def set_admin_flash(token: str, key: str, vars: dict[str, str] | None = None) -> None:
    if key:
        ADMIN_FLASH[token] = json.dumps({"k": key, "v": vars or {}})


def store_admin_flash(token: str, message: str) -> None:
    if not message:
        return
    if message.startswith("{"):
        ADMIN_FLASH[token] = message
    else:
        set_admin_flash(token, message)


def pop_admin_flash(token: str) -> str:
    return ADMIN_FLASH.pop(token, "")


def admin_panel_flash(handler: BaseHTTPRequestHandler) -> str:
    token = get_admin_token(handler)
    if not token:
        return ""
    flash = pop_admin_flash(token)
    if flash:
        return flash
    qs = parse_qs(urlparse(handler.path).query)
    legacy = qs.get("msg", [""])[0]
    return legacy


def adminT(lang: str, key: str, **vars: str) -> str:
    parts = key.split(".")
    value: Any = ADMIN_I18N.get(lang, ADMIN_I18N["nl"])
    for part in parts:
        if not isinstance(value, dict):
            return key
        value = value.get(part)
    if not isinstance(value, str):
        return key
    text = value
    for name, val in vars.items():
        text = text.replace(f"{{{name}}}", str(val))
    return text


def admin_flash_html(raw: str) -> str:
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict) and payload.get("k"):
            return render_admin_flash(str(payload["k"]), payload.get("v") or {})
    except (json.JSONDecodeError, TypeError):
        pass
    if "." in raw and not raw.startswith("{"):
        return render_admin_flash(raw, {})
    return f'<p class="ok">{html.escape(raw)}</p>'


def render_admin_flash(key: str, vars: dict[str, Any]) -> str:
    str_vars = {k: str(v) for k, v in vars.items()}
    role_key = str_vars.pop("roleKey", "")
    text = adminT("nl", key, role=adminT("nl", f"roles.{role_key}") if role_key else "", **str_vars)
    attrs = " ".join(
        f'data-i18n-var-{html.escape(k)}="{html.escape(v)}"' for k, v in str_vars.items()
    )
    role_attr = (
        f' data-i18n-var-role-key="{html.escape(role_key)}"' if role_key else ""
    )
    return (
        f'<p class="ok" data-i18n-admin="{html.escape(key)}" {attrs}{role_attr}>'
        f"{html.escape(text)}</p>"
    )


def re_fullmatch_hex64(token: str) -> bool:
    return len(token) == 64 and bool(re.fullmatch(r"[a-f0-9]{64}", token))


def get_admin_token(handler: BaseHTTPRequestHandler) -> str | None:
    cookie = handler.headers.get("Cookie", "")
    prefix = ADMIN_COOKIE + "="
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith(prefix):
            token = part[len(prefix) :]
            if re_fullmatch_hex64(token):
                return token
    return None


def get_admin_session(handler: BaseHTTPRequestHandler) -> dict[str, Any] | None:
    purge_admin_sessions()
    token = get_admin_token(handler)
    if not token:
        return None
    session = ADMIN_SESSIONS.get(token)
    if not session or session.get("expires", 0) <= time.time():
        ADMIN_SESSIONS.pop(token, None)
        ADMIN_FLASH.pop(token, None)
        return None
    return session


def admin_authenticated(handler: BaseHTTPRequestHandler) -> bool:
    return get_admin_session(handler) is not None


def is_owner_role(role: str) -> bool:
    return normalize_admin_role(role) == "owner"


def is_owner_session(session: dict[str, Any]) -> bool:
    return is_owner_role(session.get("role", ""))


def is_administrator_session(session: dict[str, Any]) -> bool:
    return normalize_session_role(session.get("role", "")) == "administrator"


def is_superadmin_session(session: dict[str, Any]) -> bool:
    return normalize_session_role(session.get("role", "")) == "superadmin"


def roles_for_session(session: dict[str, Any] | None) -> tuple[str, ...]:
    if not session:
        return ()
    if is_owner_session(session):
        return ADMIN_ROLES
    if is_superadmin_session(session):
        return ("administrator", "moderator")
    if is_administrator_session(session):
        return ("moderator",)
    return ()


def resolve_assignable_admin_role(
    session: dict[str, Any], raw_role: str
) -> tuple[str | None, str | None]:
    role = normalize_admin_role(raw_role)
    if not role:
        return None, "flash.invalidRole"
    if role not in roles_for_session(session):
        if is_owner_role(role):
            return None, "flash.onlyOwnerAssign"
        if is_superadmin_session(session):
            return None, "flash.superadminRoleLimit"
        if is_administrator_session(session):
            return None, "flash.adminOnlyModerator"
        return None, "flash.noRolePermission"
    return role, None


def resolve_create_admin_role(
    session: dict[str, Any], raw_role: str
) -> tuple[str | None, str | None]:
    if is_administrator_session(session):
        posted = normalize_admin_role(raw_role)
        if posted and posted != "moderator":
            return None, "flash.adminOnlyModerator"
        return "moderator", None
    return resolve_assignable_admin_role(session, raw_role)


def can_write_admin(session: dict[str, Any]) -> bool:
    return normalize_session_role(session.get("role", "")) in (
        "owner",
        "superadmin",
        "administrator",
    )


def can_moderate_admin(session: dict[str, Any]) -> bool:
    return normalize_session_role(session.get("role", "")) in (
        "owner",
        "superadmin",
        "administrator",
        "moderator",
    )


def can_manage_admin_users(session: dict[str, Any]) -> bool:
    return normalize_session_role(session.get("role", "")) in (
        "owner",
        "superadmin",
        "administrator",
    )


def can_change_admin_roles(session: dict[str, Any]) -> bool:
    return normalize_session_role(session.get("role", "")) in ("owner", "superadmin")


def can_delete_admin_target(session: dict[str, Any], target_role: str) -> bool:
    actor = normalize_session_role(session.get("role", ""))
    target = normalize_admin_role(target_role) or target_role
    if actor == "owner":
        return True
    if actor == "superadmin":
        return target in ("administrator", "moderator")
    if actor == "administrator":
        return target == "moderator"
    return False


def can_reset_admin_password(session: dict[str, Any], target_role: str) -> bool:
    return can_delete_admin_target(session, target_role)


def can_edit_admin_target(session: dict[str, Any], target_role: str) -> bool:
    if not can_change_admin_roles(session):
        return False
    target = normalize_admin_role(target_role) or target_role
    if target in ("owner", "superadmin"):
        return is_owner_session(session)
    if is_superadmin_session(session):
        return target in ("administrator", "moderator")
    return True


def create_admin_session(
    *,
    admin_id: str | None,
    username: str,
    role: str,
    must_change_password: bool = False,
) -> str:
    token = secrets.token_hex(32)
    ADMIN_SESSIONS[token] = {
        "expires": time.time() + ADMIN_SESSION_HOURS * 3600,
        "admin_id": admin_id,
        "username": username,
        "role": role,
        "must_change_password": must_change_password,
    }
    return token


def admin_post_login_path(session: dict[str, Any]) -> str:
    if session.get("must_change_password"):
        return ADMIN_CHANGE_PASSWORD_PATH
    return ADMIN_PANEL_PATH


def require_admin_password_changed(
    handler: BaseHTTPRequestHandler, session: dict[str, Any] | None, path: str
) -> bool:
    if not session or not session.get("must_change_password"):
        return False
    if path in (ADMIN_CHANGE_PASSWORD_PATH, "/admin/logout"):
        return False
    admin_redirect(handler, ADMIN_CHANGE_PASSWORD_PATH)
    return True


def authenticate_admin_user(
    conn: sqlite3.Connection, username: str, password: str
) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT * FROM admin_users WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()
    if not row:
        return None
    if not verify_admin_password_hash(password, row["password_salt"], row["password_hash"]):
        return None
    conn.execute(
        "UPDATE admin_users SET last_login = ? WHERE id = ?",
        (utc_now_iso(), row["id"]),
    )
    conn.commit()
    return row


def resolve_admin_login(
    conn: sqlite3.Connection, username: str, password: str
) -> tuple[str | None, str, str, bool] | None:
    username = username.strip()
    if not password:
        return None
    if username:
        row = authenticate_admin_user(conn, username, password)
        if row:
            role = normalize_admin_role(row["role"]) or row["role"]
            must_change = bool(row["must_change_password"]) if "must_change_password" in row.keys() else False
            return row["id"], row["username"], role, must_change
        if username.lower() == "admin" and verify_env_admin_password(password):
            admin_id = upsert_bootstrap_admin(conn)
            return admin_id, "admin", "owner", False
        return None
    if verify_env_admin_password(password):
        admin_id = upsert_bootstrap_admin(conn)
        return admin_id, "admin", "owner", False
    return None


def admin_cookie_header(token: str) -> str:
    secure = "; Secure" if os.environ.get("RACKFORGE_SECURE_COOKIE", "1") == "1" else ""
    return (
        f"{ADMIN_COOKIE}={token}; Path=/admin; HttpOnly; SameSite=Strict; "
        f"Max-Age={ADMIN_SESSION_HOURS * 3600}{secure}"
    )


def clear_admin_cookie_header() -> str:
    secure = "; Secure" if os.environ.get("RACKFORGE_SECURE_COOKIE", "1") == "1" else ""
    return f"{ADMIN_COOKIE}=; Path=/admin; HttpOnly; SameSite=Strict; Max-Age=0{secure}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()


def fmt_time(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return html.escape(str(iso))


def admin_i18n_script() -> str:
    payload = json.dumps(ADMIN_I18N, ensure_ascii=False)
    boot = ADMIN_I18N_BOOT.replace("__ADMIN_MESSAGES__", payload)
    return f"<script>{boot}</script>"


def admin_lang_select() -> str:
    return """<label class="admin-lang">
      <span data-i18n-admin="language">Taal</span>
      <select id="admin-lang-select" class="admin-lang__select"
        data-i18n-admin-attr="aria-label" data-i18n-admin="language">
        <option value="nl">NL</option>
        <option value="en">EN</option>
      </select>
    </label>"""


def page_shell(
    title: str,
    body: str,
    *,
    with_js: bool = False,
    page_title_key: str = "",
    auth_layout: bool = False,
) -> str:
    script = admin_i18n_script()
    if with_js:
        script += f"<script>{ADMIN_JS}</script>"
    title_attr = ""
    if page_title_key:
        title_attr = f' data-admin-page-title="{html.escape(page_title_key)}"'
    body_attr = ' class="admin-auth"' if auth_layout else ""
    wrap_class = "wrap admin-auth__wrap" if auth_layout else "wrap"
    bg = ADMIN_AUTH_BACKGROUND if auth_layout else ""
    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex, nofollow">
  <title{title_attr}>{html.escape(title)} — RackForge Panel</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>{BASE_STYLE}</style>
</head>
<body{body_attr}>{bg}<div class="{wrap_class}">{body}</div>{script}</body></html>"""


def admin_auth_showcase() -> str:
    return f"""
    <section class="admin-auth__showcase" aria-hidden="true">
      <div class="admin-auth__showcase-brand">
        <span class="admin-auth__logo" aria-hidden="true">{ADMIN_AUTH_LOGO_SVG}</span>
        <div class="admin-auth__showcase-text">
          <div class="admin-auth__showcase-title">RackForge <span>Panel</span></div>
          <div class="admin-auth__showcase-sub" data-i18n-admin="login.controlCenter">Beheeromgeving</div>
          <p class="admin-auth__showcase-tagline" data-i18n-admin="login.asideTagline">
            Intern beheer van gebruikers, racks en data.</p>
        </div>
      </div>
    </section>"""


def admin_auth_panel_wrap(
    content: str,
    *,
    title_key: str,
    title_text: str,
    subtitle_key: str = "",
    subtitle_text: str = "",
    subtitle_vars: dict[str, str] | None = None,
    show_footer: bool = True,
) -> str:
    subtitle = ""
    if subtitle_key:
        vars_attrs = ""
        for key, value in (subtitle_vars or {}).items():
            vars_attrs += f' data-i18n-var-{html.escape(key)}="{html.escape(value)}"'
        subtitle = (
            f'<p class="admin-auth__subtitle" data-i18n-admin="{html.escape(subtitle_key)}"'
            f"{vars_attrs}>{html.escape(subtitle_text)}</p>"
        )
    footer = ""
    if show_footer:
        footer = (
            '<p class="admin-auth__footer" data-i18n-admin="login.staffOnly">'
            "Alleen geautoriseerd personeel</p>"
        )
    return f"""
    <div class="admin-auth__panel" role="main">
      <div class="admin-auth__panel-bar">
        <div class="admin-auth__panel-status">
          <span class="admin-auth__status-dot" aria-hidden="true"></span>
          <span data-i18n-admin="login.secureAccess">Beveiligde toegang</span>
        </div>
        {admin_lang_select()}
      </div>
      <div class="admin-auth__panel-body">
        <div class="admin-auth__panel-head">
          <div class="admin-auth__panel-meta">
            <span class="admin-auth__session-badge" data-i18n-admin="login.sessionLabel">Paneelsessie</span>
          </div>
          <h2 class="admin-auth__title" data-i18n-admin="{html.escape(title_key)}">{html.escape(title_text)}</h2>
          {subtitle}
        </div>
        {content}
        {footer}
      </div>
    </div>"""


def admin_auth_frame(panel_html: str) -> str:
    return f"""
    <div class="admin-auth__gate">
      <div class="admin-auth__layout">
        {admin_auth_showcase()}
        {panel_html}
      </div>
    </div>"""


def login_page(
    error: str = "", *, available: bool = True, reset_ok: bool = False
) -> str:
    err = ""
    if reset_ok:
        err = (
            '<p class="ok" data-i18n-admin="login.resetSuccess">'
            "Wachtwoord bijgewerkt. Je kunt nu inloggen.</p>"
        )
    elif error:
        err = (
            '<p class="err" data-i18n-admin="login.wrongCredentials">'
            f"{html.escape(error)}</p>"
        )
    if not available:
        err = (
            '<p class="err" data-i18n-admin="login.notConfigured">'
            "Admin niet geconfigureerd. "
            "Voeg een admin-gebruiker toe of zet RACKFORGE_ADMIN_PASSWORD in "
            "~/.config/rackforge/admin.env.</p>"
        )
    forgot_link = ""
    if available:
        forgot_link = f"""
        <p class="admin-auth__forgot">
          <a href="{ADMIN_FORGOT_PATH}" data-i18n-admin="login.forgotPassword">Wachtwoord vergeten?</a>
        </p>"""
    panel = f"""
      <form class="admin-auth__form" method="post" action="/admin/login">
        <label for="username" data-i18n-admin="username">Gebruikersnaam</label>
        <input type="text" id="username" name="username" autocomplete="username" required>
        <label for="password" data-i18n-admin="password">Wachtwoord</label>
        <input type="password" id="password" name="password" autocomplete="current-password" required>
        {err}
        <button class="btn btn--primary" type="submit"
          data-i18n-admin="login" {"disabled" if not available else ""}>Inloggen</button>
      </form>
      {forgot_link}"""
    body = admin_auth_frame(
        admin_auth_panel_wrap(
            panel,
            title_key="login.title",
            title_text="Inloggen",
            subtitle_key="dbManagement",
            subtitle_text="Databasebeheer",
        )
    )
    return page_shell("Inloggen", body, page_title_key="login.title", auth_layout=True)


def admin_auth_notice(
    error_key: str = "",
    *,
    ok_key: str = "",
    i18n_vars: dict[str, str] | None = None,
) -> str:
    vars_attrs = ""
    for key, value in (i18n_vars or {}).items():
        vars_attrs += f' data-i18n-var-{html.escape(key)}="{html.escape(value)}"'
    if ok_key:
        return (
            f'<p class="ok" data-i18n-admin="{html.escape(ok_key)}"{vars_attrs}>'
            f"{html.escape(adminT('nl', ok_key))}</p>"
        )
    if error_key:
        return (
            f'<p class="err" data-i18n-admin="{html.escape(error_key)}"{vars_attrs}>'
            f"{html.escape(adminT('nl', error_key))}</p>"
        )
    return ""


def forgot_password_request_page(error_key: str = "") -> str:
    panel = f"""
      {admin_auth_notice(error_key)}
      <form class="admin-auth__form" method="post" action="{ADMIN_FORGOT_PATH}">
        <label for="username" data-i18n-admin="username">Gebruikersnaam</label>
        <input type="text" id="username" name="username" autocomplete="username" required>
        <button class="btn btn--primary" type="submit"
          data-i18n-admin="forgotPassword.submit">Resetcode versturen</button>
      </form>
      <a class="btn btn--ghost" href="{ADMIN_LOGIN_PATH}"
        data-i18n-admin="forgotPassword.backToLogin">Terug naar inloggen</a>"""
    body = admin_auth_frame(
        admin_auth_panel_wrap(
            panel,
            title_key="forgotPassword.title",
            title_text="Wachtwoord vergeten",
            subtitle_key="forgotPassword.subtitle",
            subtitle_text="Vul je panel-gebruikersnaam in. We sturen een code naar het gekoppelde e-mailadres.",
        )
    )
    return page_shell(
        "Wachtwoord vergeten", body, page_title_key="forgotPassword.title", auth_layout=True
    )


def forgot_password_verify_page(
    username: str,
    masked_email: str,
    *,
    error_key: str = "",
    ok_key: str = "",
) -> str:
    ok_block = (
        admin_auth_notice(ok_key=ok_key, i18n_vars={"email": masked_email})
        if ok_key
        else ""
    )
    err_block = admin_auth_notice(error_key) if error_key else ""
    subtitle = (
        f"Voer de 6-cijferige code in die we naar {masked_email} hebben gestuurd."
    )
    panel = f"""
      {ok_block}{err_block}
      <form class="admin-auth__form" method="post" action="{ADMIN_FORGOT_VERIFY_PATH}">
        <input type="hidden" name="username" value="{html.escape(username)}">
        <label for="code" data-i18n-admin="forgotPassword.code">Verificatiecode</label>
        <input type="text" id="code" name="code" inputmode="numeric" pattern="[0-9]{{6}}"
          maxlength="6" minlength="6" autocomplete="one-time-code" required>
        <button class="btn btn--primary" type="submit"
          data-i18n-admin="forgotPassword.verifySubmit">Code bevestigen</button>
      </form>
      <a class="btn btn--ghost" href="{ADMIN_LOGIN_PATH}"
        data-i18n-admin="forgotPassword.backToLogin">Terug naar inloggen</a>"""
    body = admin_auth_frame(
        admin_auth_panel_wrap(
            panel,
            title_key="forgotPassword.verifyTitle",
            title_text="Code invoeren",
            subtitle_key="forgotPassword.verifySubtitle",
            subtitle_text=subtitle,
            subtitle_vars={"email": masked_email},
        )
    )
    return page_shell(
        "Code invoeren", body, page_title_key="forgotPassword.verifyTitle", auth_layout=True
    )


def admin_reset_password_page(token: str, error_key: str = "") -> str:
    panel = f"""
      {admin_auth_notice(error_key)}
      <form class="admin-auth__form" method="post" action="{ADMIN_RESET_PATH}">
        <input type="hidden" name="token" value="{html.escape(token)}">
        <label for="password" data-i18n-admin="changePassword.newPassword">Nieuw wachtwoord</label>
        <input type="password" id="password" name="password" autocomplete="new-password" required>
        <label for="password_confirm" data-i18n-admin="changePassword.confirmPassword">Bevestig wachtwoord</label>
        <input type="password" id="password_confirm" name="password_confirm"
          autocomplete="new-password" required>
        <button class="btn btn--primary" type="submit"
          data-i18n-admin="forgotPassword.resetSubmit">Wachtwoord opslaan</button>
      </form>
      <a class="btn btn--ghost" href="{ADMIN_LOGIN_PATH}"
        data-i18n-admin="forgotPassword.backToLogin">Terug naar inloggen</a>"""
    body = admin_auth_frame(
        admin_auth_panel_wrap(
            panel,
            title_key="forgotPassword.resetTitle",
            title_text="Nieuw wachtwoord",
            subtitle_key="forgotPassword.resetSubtitle",
            subtitle_text="Kies een nieuw wachtwoord voor het panel.",
        )
    )
    return page_shell(
        "Nieuw wachtwoord", body, page_title_key="forgotPassword.resetTitle", auth_layout=True
    )


def change_password_page(error_key: str = "", *, voluntary: bool = False) -> str:
    err = ""
    if error_key:
        err = (
            f'<p class="err" data-i18n-admin="{html.escape(error_key)}">'
            f"{html.escape(adminT('nl', error_key))}</p>"
        )
    subtitle_key = (
        "changePassword.voluntarySubtitle"
        if voluntary
        else "changePassword.subtitle"
    )
    subtitle_text = (
        "Wijzig je panelwachtwoord."
        if voluntary
        else "Kies een nieuw wachtwoord om verder te gaan in het panel."
    )
    current_field = ""
    if voluntary:
        current_field = """
        <label for="current_password" data-i18n-admin="changePassword.currentPassword">
          Huidig wachtwoord</label>
        <input type="password" id="current_password" name="current_password"
          autocomplete="current-password" required>"""
    back_link = ""
    if voluntary:
        back_link = f"""
        <a class="btn btn--ghost" href="{ADMIN_PANEL_PATH}"
          data-i18n-admin="changePassword.back">Terug naar panel</a>"""
    panel = f"""
      {err}
      <form class="admin-auth__form" method="post" action="{ADMIN_CHANGE_PASSWORD_PATH}">
        {current_field}
        <label for="password" data-i18n-admin="changePassword.newPassword">Nieuw wachtwoord</label>
        <input type="password" id="password" name="password" autocomplete="new-password" required>
        <label for="password_confirm" data-i18n-admin="changePassword.confirmPassword">Bevestig wachtwoord</label>
        <input type="password" id="password_confirm" name="password_confirm"
          autocomplete="new-password" required>
        <button class="btn btn--primary" type="submit"
          data-i18n-admin="changePassword.save">Wachtwoord opslaan</button>
      </form>
      {back_link}"""
    body = admin_auth_frame(
        admin_auth_panel_wrap(
            panel,
            title_key="changePassword.title",
            title_text="Nieuw wachtwoord instellen",
            subtitle_key=subtitle_key,
            subtitle_text=subtitle_text,
        )
    )
    return page_shell(
        "Wachtwoord wijzigen",
        body,
        page_title_key="changePassword.title",
        auth_layout=True,
    )


def role_select(
    name: str,
    selected: str = "administrator",
    *,
    track_changes: bool = False,
    session: dict[str, Any] | None = None,
) -> str:
    selected = normalize_admin_role(selected) or "administrator"
    roles = roles_for_session(session)
    options = "".join(
        f'<option value="{html.escape(role)}" data-i18n-admin="roles.{html.escape(role)}"'
        f'{" selected" if role == selected else ""}>'
        f"{html.escape(role_label(role))}</option>"
        for role in roles
    )
    extra = ""
    if track_changes:
        extra = (
            f' class="admin-role-select" data-initial="{html.escape(selected)}"'
        )
    return f'<select name="{html.escape(name)}" required{extra}>{options}</select>'


def action_form(
    action: str,
    fields: dict[str, str],
    label: str,
    btn_class: str = "btn--ghost",
    *,
    return_to: str = "",
    confirm_key: str = "",
) -> str:
    inputs = "".join(
        f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">'
        for k, v in fields.items()
    )
    return_to_field = ""
    if return_to:
        return_to_field = (
            f'<input type="hidden" name="return_to" value="{html.escape(return_to)}">'
        )
    if confirm_key:
        confirm_attr = f' onsubmit="return confirmAdminAction({json.dumps(confirm_key)});"'
    else:
        confirm_attr = f' onsubmit="return confirm({json.dumps(label + " — doorgaan?")});"'
    i18n_attr = ""
    if confirm_key:
        i18n_attr = f' data-i18n-admin="{html.escape(confirm_key)}"'
    return f"""
    <form method="post" action="/admin/action" class="actions__form"{confirm_attr}>
      <input type="hidden" name="action" value="{html.escape(action)}">
      {return_to_field}
      {inputs}
      <button type="submit" class="btn btn--sm {btn_class}"{i18n_attr}>{html.escape(label)}</button>
    </form>"""


def admin_password_reset_form(
    admin_id: str,
    *,
    return_to: str = "",
) -> str:
    return_to_field = ""
    if return_to:
        return_to_field = (
            f'<input type="hidden" name="return_to" value="{html.escape(return_to)}">'
        )
    return f"""
    <form method="post" action="/admin/action" class="actions__form admin-reset-form"
      onsubmit="return confirmAdminAction('usersPage.resetPassword');">
      <input type="hidden" name="action" value="require_admin_password_reset">
      {return_to_field}
      <input type="hidden" name="admin_id" value="{html.escape(admin_id)}">
      <input type="password" name="password" required autocomplete="new-password"
        data-i18n-admin="usersPage.resetPasswordNew" data-i18n-admin-attr="placeholder"
        aria-label="Nieuw wachtwoord">
      <button type="submit" class="btn btn--sm btn--ghost" data-i18n-admin="usersPage.resetPassword">
        Wachtwoord resetten</button>
    </form>"""


def admin_nav(session: dict[str, Any], active: str) -> str:
    links = [
        ("panel", "Dashboard", ADMIN_PANEL_PATH),
    ]
    if can_manage_admin_users(session):
        links.append(("users", "Gebruikers", ADMIN_USERS_PATH))
    nav_keys = {"panel": "nav.dashboard", "users": "nav.adminUsers"}
    items = []
    for key, label, href in links:
        current = ' aria-current="page"' if key == active else ""
        i18n_key = nav_keys.get(key, "")
        i18n_attr = f' data-i18n-admin="{i18n_key}"' if i18n_key else ""
        items.append(
            f'<a class="btn btn--ghost btn--sm" href="{html.escape(href)}"{current}{i18n_attr}>'
            f"{html.escape(label)}</a>"
        )
    return (
        f'<nav class="admin-nav" aria-label="Admin navigatie" '
        f'data-i18n-admin-attr="aria-label" data-i18n-admin="nav.aria">{"".join(items)}</nav>'
    )


def admin_topbar(
    session: dict[str, Any],
    title: str,
    subtitle: str,
    *,
    title_key: str = "",
    subtitle_key: str = "",
) -> str:
    who = html.escape(str(session.get("username", "—")))
    role = html.escape(role_label(str(session.get("role", ""))))
    title_attr = f' data-i18n-admin="{title_key}"' if title_key else ""
    subtitle_html = html.escape(subtitle)
    if subtitle_key:
        subtitle_html = (
            f'<span data-i18n-admin="{subtitle_key}">{html.escape(subtitle)}</span>'
        )
    return f"""
    <div class="topbar">
      <div>
        <h1{title_attr}>{html.escape(title)}</h1>
        <p class="sub">{subtitle_html} · {who} ({role})</p>
      </div>
      <div class="topbar__actions">
        {admin_lang_select()}
        {'' if session.get('must_change_password') else f'<a class="btn btn--ghost" href="{ADMIN_CHANGE_PASSWORD_PATH}" data-i18n-admin="account.changePassword">Wachtwoord wijzigen</a>'}
        <form method="post" action="/admin/logout">
          <button class="btn btn--ghost" type="submit" data-i18n-admin="logout">Uitloggen</button>
        </form>
      </div>
    </div>"""


def admin_action_return_to(form: dict[str, str], action: str) -> str:
    if action in ADMIN_USER_ACTIONS:
        return ADMIN_USERS_PATH
    target = (form.get("return_to") or "").strip()
    if target.startswith("/admin/"):
        return target
    return ADMIN_PANEL_PATH


def remove_avatar_files(user_id: str) -> None:
    for ext in ("jpg", "jpeg", "png", "webp", "gif"):
        path = os.path.join(AVATAR_DIR, f"{user_id}.{ext}")
        if os.path.isfile(path):
            os.remove(path)


def device_summary(devices_json: str, limit: int = 4) -> str:
    try:
        devices = json.loads(devices_json)
    except (TypeError, json.JSONDecodeError):
        return "—"
    if not isinstance(devices, list) or not devices:
        return '<span data-i18n-admin="common.empty">leeg</span>'
    names: list[str] = []
    for dev in devices[:limit]:
        if isinstance(dev, dict):
            label = dev.get("name") or dev.get("type") or dev.get("id") or "?"
            names.append(str(label))
    extra = len(devices) - limit
    text = ", ".join(names)
    if extra > 0:
        text += f" (+{extra})"
    return html.escape(text)


def collect_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    now = utc_now_iso()
    week_ago = iso_days_ago(7)
    month_ago = iso_days_ago(30)
    return {
        "users": conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"],
        "blocked": conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE blocked = 1"
        ).fetchone()["n"],
        "plans": conn.execute("SELECT COUNT(*) AS n FROM plans").fetchone()["n"],
        "sessions": conn.execute(
            "SELECT COUNT(*) AS n FROM sessions WHERE expires_at >= ?", (now,)
        ).fetchone()["n"],
        "google": conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE google_id IS NOT NULL"
        ).fetchone()["n"],
        "pending_verify": conn.execute(
            "SELECT COUNT(*) AS n FROM email_verifications WHERE expires_at >= ?",
            (now,),
        ).fetchone()["n"],
        "pending_reset": conn.execute(
            "SELECT COUNT(*) AS n FROM password_resets WHERE expires_at >= ?",
            (now,),
        ).fetchone()["n"],
        "oauth_states": conn.execute(
            "SELECT COUNT(*) AS n FROM oauth_states WHERE expires_at >= ?", (now,)
        ).fetchone()["n"],
        "new_7d": conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE created_at >= ?", (week_ago,)
        ).fetchone()["n"],
        "new_30d": conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE created_at >= ?", (month_ago,)
        ).fetchone()["n"],
        "active_7d": conn.execute(
            """
            SELECT COUNT(DISTINCT user_id) AS n FROM sessions
            WHERE created_at >= ?
            """,
            (week_ago,),
        ).fetchone()["n"],
    }


def weekly_chart(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """
        SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n
        FROM users
        WHERE created_at >= ?
        GROUP BY day
        ORDER BY day DESC
        LIMIT 14
        """
        ,
        (iso_days_ago(14),),
    ).fetchall()
    if not rows:
        return (
            "<p class='sub' data-i18n-admin='tables.noRegistrations'>"
            "Geen registraties in de laatste 14 dagen.</p>"
        )
    max_n = max(r["n"] for r in rows) or 1
    bars = ""
    for row in reversed(rows):
        pct = int((row["n"] / max_n) * 100)
        bars += f"""
        <div class="week-bar">
          <span class="mono" style="width:5.5rem;">{html.escape(row["day"])}</span>
          <div class="week-bar__track"><div class="week-bar__fill" style="width:{pct}%"></div></div>
          <span class="mono">{row["n"]}</span>
        </div>"""
    return f'<div class="week-bars">{bars}</div>'


def avatar_cell(user_id: str, avatar_ext: str | None, avatar_updated: str | None) -> str:
    if avatar_ext and avatar_updated:
        v = html.escape(avatar_updated)
        src = f"{APP_URL}/api/avatars/{html.escape(user_id)}?v={v}"
        return f'<img class="avatar" src="{src}" alt="">'
    return '<span class="avatar avatar--empty" aria-hidden="true"></span>'


def admin_users_permissions_help() -> str:
    roles = (
        ("perms.ownerTitle", ("perms.ownerCreate", "perms.ownerEdit", "perms.ownerDelete")),
        (
            "perms.superadminTitle",
            ("perms.superadminCreate", "perms.superadminEdit", "perms.superadminDelete"),
        ),
        ("perms.adminTitle", ("perms.adminCreate", "perms.adminEdit", "perms.adminDelete")),
        ("perms.moderatorTitle", ("perms.moderatorNone",)),
    )
    items = []
    for title_key, line_keys in roles:
        list_items = "".join(
            f'<li data-i18n-admin="{html.escape(key)}">{html.escape(adminT("nl", key))}</li>'
            for key in line_keys
        )
        items.append(
            f"""<div class="role-perms__item">
          <div class="role-perms__title" data-i18n-admin="{html.escape(title_key)}">"""
            f"""{html.escape(adminT("nl", title_key))}</div>
          <ul class="role-perms__list">{list_items}</ul>
        </div>"""
        )
    return f"""<div class="sub" style="margin-top:0.65rem;">
      <strong data-i18n-admin="usersPage.permissionsTitle">Rechtenoverzicht</strong>
      <div class="role-perms">{"".join(items)}</div>
    </div>"""


def admin_users_page(
    conn: sqlite3.Connection,
    flash: str = "",
    session: dict[str, Any] | None = None,
) -> str:
    session = session or {}
    now = fmt_time(utc_now_iso())
    flash_html = admin_flash_html(flash)
    rows = conn.execute(
        """
        SELECT a.id, a.username, a.role, a.created_at, a.last_login, a.app_user_id,
               a.must_change_password, a.email AS admin_email, u.email AS app_email
        FROM admin_users a
        LEFT JOIN users u ON u.id = a.app_user_id
        ORDER BY a.created_at ASC
        """
    ).fetchall()
    body = ""
    current_id = session.get("admin_id")
    return_to = ADMIN_USERS_PATH
    for row in rows:
        role = row["role"]
        normalized_role = normalize_admin_role(role) or role
        email_display = (row["admin_email"] or row["app_email"] or "").strip()
        search = f"{row['username']} {role} {email_display}".lower()
        if can_edit_admin_target(session, role):
            role_form = f"""
        <form method="post" action="/admin/action" class="actions__form admin-role-form" style="display:inline;">
          <input type="hidden" name="action" value="update_admin_role">
          <input type="hidden" name="return_to" value="{html.escape(return_to)}">
          <input type="hidden" name="admin_id" value="{html.escape(row['id'])}">
          {role_select("role", role, track_changes=True, session=session)}
          <button type="submit" class="btn btn--sm btn--ghost admin-role-save" hidden disabled
            data-i18n-admin="usersPage.save">Opslaan</button>
        </form>"""
        else:
            norm = normalize_admin_role(role) or role
            role_form = (
                f'<span class="pill admin-role-pill" data-admin-role="{html.escape(norm)}">'
                f"{html.escape(role_label(role))}</span>"
            )
        reset_btn = ""
        if row["id"] != current_id and can_reset_admin_password(session, role):
            reset_btn = admin_password_reset_form(row["id"], return_to=return_to)
        delete_btn = ""
        if row["id"] != current_id and can_delete_admin_target(session, role):
            delete_btn = action_form(
                "delete_admin_user",
                {"admin_id": row["id"]},
                "Verwijderen",
                "btn--danger",
                return_to=return_to,
                confirm_key="usersPage.delete",
            )

        email_hint = ""
        if email_display:
            email_hint = f'<div class="sub">{html.escape(email_display)}</div>'
        pwd_hint = ""
        if row["must_change_password"]:
            pwd_hint = (
                ' <span class="pill pill--warn" data-i18n-admin="usersPage.passwordChangeRequired">'
                "Wachtwoord wijzigen</span>"
            )
        body += f"""<tr data-search="{html.escape(search)}">
          <td>{html.escape(row["username"])}{pwd_hint}{email_hint}</td>
          <td><span class="pill admin-role-pill" data-admin-role="{html.escape(normalized_role)}">{html.escape(role_label(role))}</span></td>
          <td>{fmt_time(row["created_at"])}</td>
          <td>{fmt_time(row["last_login"])}</td>
          <td><div class="actions">{role_form}{reset_btn}{delete_btn}</div></td>
        </tr>"""
    if not body:
        body = (
            '<tr><td colspan="5" data-i18n-admin="usersPage.empty">'
            "Nog geen admin-gebruikers in de database</td></tr>"
        )
    if is_administrator_session(session):
        create_role_field = f"""<label><span data-i18n-admin="usersPage.role">Rol</span>
          <input type="text" value="{html.escape(role_label("moderator"))}" disabled
            data-i18n-admin="roles.moderator">
          <input type="hidden" name="role" value="moderator">
        </label>"""
    elif can_change_admin_roles(session):
        create_role_field = f"""<label><span data-i18n-admin="usersPage.role">Rol</span>
          {role_select("role", "administrator", session=session)}
        </label>"""
    else:
        create_role_field = ""
    create_form = f"""
    <form method="post" action="/admin/action" class="card" style="margin-bottom:1rem;">
      <input type="hidden" name="action" value="create_admin_user">
      <input type="hidden" name="return_to" value="{html.escape(return_to)}">
      <h3 style="margin-bottom:0.75rem;font-size:0.95rem;" data-i18n-admin="usersPage.addTitle">
        Admin-gebruiker toevoegen</h3>
      <div class="inline-form">
        <label><span data-i18n-admin="username">Gebruikersnaam</span>
          <input type="text" name="username" pattern="[a-zA-Z0-9_]{{3,32}}" required>
        </label>
        <label><span data-i18n-admin="usersPage.email">E-mail</span>
          <input type="email" name="email" autocomplete="email" required>
        </label>
        <label><span data-i18n-admin="password">Wachtwoord</span>
          <input type="password" name="password" required>
        </label>
        {create_role_field}
        <label class="admin-check" style="display:flex;align-items:center;gap:0.45rem;margin-bottom:0.65rem;">
          <input type="checkbox" name="require_password_change" value="1">
          <span data-i18n-admin="usersPage.requirePasswordChange">
            Nieuw wachtwoord verplicht bij eerste login</span>
        </label>
        <button type="submit" class="btn btn--primary" data-i18n-admin="usersPage.add">Toevoegen</button>
      </div>
    </form>"""
    content = f"""
    {admin_topbar(session, "Gebruikers", "Rollen en toegang", title_key="usersPage.title", subtitle_key="usersPage.subtitle")}
    <p class="sub" style="margin:-0.75rem 0 1rem;">{html.escape(now)}</p>
    {admin_nav(session, "users")}
    {flash_html}
    <div class="toolbar">
      <input type="search" id="admin-search" data-i18n-admin-attr="placeholder"
        data-i18n-admin="usersPage.search" placeholder="Zoeken op gebruikersnaam of rol…">
    </div>
    {create_form}
    <div class="table-wrap"><table>
      <thead><tr>
        <th data-i18n-admin="usersPage.colUsername">Gebruikersnaam</th>
        <th data-i18n-admin="usersPage.colRole">Rol</th>
        <th data-i18n-admin="usersPage.colCreated">Aangemaakt</th>
        <th data-i18n-admin="usersPage.colLastLogin">Laatste login</th>
        <th data-i18n-admin="usersPage.colActions">Acties</th>
      </tr></thead>
      <tbody>{body}</tbody>
    </table></div>
    {admin_users_permissions_help()}"""
    return page_shell(
        "Gebruikers", content, with_js=True, page_title_key="usersPage.title"
    )


def users_table(
    conn: sqlite3.Connection, *, writable: bool = True, moderate: bool = True
) -> str:
    rows = conn.execute(
        """
        SELECT u.*,
               (SELECT MAX(s.created_at) FROM sessions s WHERE s.user_id = u.id) AS last_login,
               (SELECT COUNT(*) FROM plans p WHERE p.user_id = u.id) AS plan_count,
               (SELECT p.rack_height FROM plans p WHERE p.user_id = u.id LIMIT 1) AS rack_height,
               (SELECT p.devices FROM plans p WHERE p.user_id = u.id LIMIT 1) AS devices
        FROM users u
        ORDER BY u.created_at DESC
        """
    ).fetchall()
    body = ""
    for row in rows:
        blocked = bool(row["blocked"]) if "blocked" in row.keys() else False
        verified = (
            '<span class="pill pill--ok" data-i18n-admin="common.yes">ja</span>'
            if row["email_verified"]
            else '<span class="pill pill--warn" data-i18n-admin="common.no">nee</span>'
        )
        google = (
            '<span class="pill pill--ok">Google</span>'
            if row["google_id"]
            else "—"
        )
        block_pill = (
            '<span class="pill pill--danger" data-i18n-admin="common.blocked">geblokkeerd</span>'
            if blocked
            else ""
        )
        pw = (
            '<span data-i18n-admin="common.yes">ja</span>'
            if row["password_set"]
            else '<span data-i18n-admin="common.no">nee</span>'
        )
        search = f"{row['username'] or ''} {row['email']} {row['id']}".lower()
        rack_info = "—"
        if row["plan_count"]:
            rack_info = (
                f'{row["rack_height"] or "?"}U · '
                f'<span data-i18n-admin="common.plans" '
                f'data-i18n-var-count="{row["plan_count"]}">'
                f'{row["plan_count"]} plan(s)</span>'
            )
        devices_preview = device_summary(row["devices"] or "[]")
        block_key = "actions.unblock" if blocked else "actions.block"
        block_label = "Deblokkeren" if blocked else "Blokkeren"
        body += f"""<tr data-search="{html.escape(search)}">
          <td>{avatar_cell(row["id"], row["avatar_ext"], row["avatar_updated_at"])}</td>
          <td class="mono">{html.escape(row["username"] or "—")}</td>
          <td>{html.escape(row["email"])} {block_pill}</td>
          <td>{verified}</td>
          <td>{google}</td>
          <td>{pw}</td>
          <td>{fmt_time(row["last_login"])}</td>
          <td>{rack_info}</td>
          <td>{fmt_time(row["created_at"])}</td>
          <td>
            <div class="actions">
              {action_form("toggle_block", {"user_id": row["id"]}, block_label, "btn--ghost", confirm_key=block_key) if moderate else ""}
              {action_form("delete_user", {"user_id": row["id"]}, "Verwijderen", "btn--danger", confirm_key="actions.delete") if writable else "—"}
            </div>
            <details class="user-detail">
              <summary data-i18n-admin="actions.details">Details</summary>
              <p><span data-i18n-admin="tables.colId">ID</span>: <span class="mono">{html.escape(row["id"])}</span></p>
              <p><span data-i18n-admin="tables.colLanguage">Taal</span>: {html.escape(row["lang"] or "nl")} · Google-ID: <span class="mono">{html.escape(row["google_id"] or "—")}</span></p>
              <p><span data-i18n-admin="tables.colRackDevices">Rack</span>: {devices_preview}</p>
            </details>
          </td>
        </tr>"""
    if not body:
        body = '<tr><td colspan="10" data-i18n-admin="tables.usersEmpty">Geen gebruikers</td></tr>'
    return f"""
    <section id="users">
      <h2><span data-i18n-admin="tables.usersTitle">Gebruikers</span> ({len(rows)})</h2>
      <div class="table-wrap"><table>
        <thead><tr>
          <th></th>
          <th data-i18n-admin="tables.colName">Naam</th>
          <th data-i18n-admin="tables.colEmail">E-mail</th>
          <th data-i18n-admin="tables.colVerified">Bevestigd</th>
          <th data-i18n-admin="tables.colLogin">Login</th>
          <th data-i18n-admin="tables.colPassword">Ww</th>
          <th data-i18n-admin="tables.colLastLogin">Laatste login</th>
          <th data-i18n-admin="tables.colRack">Rack</th>
          <th data-i18n-admin="tables.colCreated">Aangemaakt</th>
          <th data-i18n-admin="tables.colActions">Acties</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table></div>
    </section>"""


def plans_table(conn: sqlite3.Connection, *, writable: bool = True) -> str:
    rows = conn.execute(
        """
        SELECT p.*, u.email AS user_email, u.username AS user_username
        FROM plans p
        LEFT JOIN users u ON u.id = p.user_id
        ORDER BY p.updated_at DESC
        """
    ).fetchall()
    body = ""
    for row in rows:
        owner = row["user_email"] or row["user_username"] or "—"
        if row["user_username"] and row["user_email"]:
            owner = f'{row["user_username"]} ({row["user_email"]})'
        devices = device_summary(row["devices"])
        search = f"{row['id']} {owner}".lower()
        body += f"""<tr data-search="{html.escape(search)}">
          <td class="mono">{html.escape(row["id"][:12])}…</td>
          <td>{row["rack_height"]}U</td>
          <td>{devices}</td>
          <td>{html.escape(str(owner))}</td>
          <td>{fmt_time(row["updated_at"])}</td>
          <td>
            {action_form("delete_plan", {"plan_id": row["id"]}, "Verwijderen", "btn--danger", confirm_key="actions.delete") if writable else "—"}
          </td>
        </tr>"""
    if not body:
        body = '<tr><td colspan="6" data-i18n-admin="tables.plansEmpty">Geen rack-plannen</td></tr>'
    return f"""
    <section id="plans">
      <h2><span data-i18n-admin="tables.plansTitle">Rack-plannen</span> ({len(rows)})</h2>
      <div class="table-wrap"><table>
        <thead><tr>
          <th data-i18n-admin="tables.colPlanId">Plan-ID</th>
          <th data-i18n-admin="tables.colHeight">Hoogte</th>
          <th data-i18n-admin="tables.colDevices">Apparaten</th>
          <th data-i18n-admin="tables.colOwner">Eigenaar</th>
          <th data-i18n-admin="tables.colUpdated">Bijgewerkt</th>
          <th data-i18n-admin="tables.colActions">Acties</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table></div>
    </section>"""


def sessions_table(
    conn: sqlite3.Connection, *, writable: bool = True, moderate: bool = True
) -> str:
    rows = conn.execute(
        """
        SELECT s.token, s.created_at, s.expires_at, u.id AS user_id, u.email, u.username
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.expires_at >= ?
        ORDER BY s.created_at DESC
        LIMIT 100
        """,
        (utc_now_iso(),),
    ).fetchall()
    body = ""
    for row in rows:
        who = row["username"] or row["email"]
        search = f"{who} {row['email']} {row['token'][:8]}".lower()
        body += f"""<tr data-search="{html.escape(search)}">
          <td>{html.escape(str(who))}</td>
          <td>{html.escape(row["email"])}</td>
          <td>{fmt_time(row["created_at"])}</td>
          <td>{fmt_time(row["expires_at"])}</td>
          <td class="mono">{html.escape(row["token"][:8])}…</td>
          <td>{action_form("revoke_session", {"token": row["token"]}, "Beëindigen", "btn--danger", confirm_key="actions.revoke") if moderate else "—"}</td>
        </tr>"""
    if not body:
        body = '<tr><td colspan="6" data-i18n-admin="tables.sessionsEmpty">Geen actieve sessies</td></tr>'
    return f"""
    <section id="sessions">
      <h2><span data-i18n-admin="tables.sessionsTitle">Actieve sessies</span> ({len(rows)})</h2>
      <div class="table-wrap"><table>
        <thead><tr>
          <th data-i18n-admin="tables.colUser">Gebruiker</th>
          <th data-i18n-admin="tables.colEmail">E-mail</th>
          <th data-i18n-admin="tables.colLoggedIn">Ingelogd</th>
          <th data-i18n-admin="tables.colExpires">Verloopt</th>
          <th data-i18n-admin="tables.colToken">Token</th>
          <th data-i18n-admin="tables.colActions">Acties</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table></div>
    </section>"""


def verifications_table(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """
        SELECT v.*, u.email AS user_email, u.username
        FROM email_verifications v
        JOIN users u ON u.id = v.user_id
        WHERE v.expires_at >= ?
        ORDER BY v.created_at DESC
        """,
        (utc_now_iso(),),
    ).fetchall()
    body = ""
    for row in rows:
        who = row["username"] or row["user_email"]
        search = f"{who} {row['email']} {row['purpose']}".lower()
        body += f"""<tr data-search="{html.escape(search)}">
          <td>{html.escape(str(who))}</td>
          <td>{html.escape(row["email"])}</td>
          <td>{html.escape(row["purpose"])}</td>
          <td>{fmt_time(row["created_at"])}</td>
          <td>{fmt_time(row["expires_at"])}</td>
          <td class="mono">{html.escape(row["token"][:8])}…</td>
        </tr>"""
    if not body:
        body = '<tr><td colspan="6" data-i18n-admin="tables.verificationsEmpty">Geen open verificaties</td></tr>'
    return f"""
    <section id="verifications">
      <h2><span data-i18n-admin="tables.verificationsTitle">Open e-mailverificaties</span> ({len(rows)})</h2>
      <div class="table-wrap"><table>
        <thead><tr>
          <th data-i18n-admin="tables.colUser">Gebruiker</th>
          <th data-i18n-admin="tables.colEmail">E-mail</th>
          <th data-i18n-admin="tables.colPurpose">Doel</th>
          <th data-i18n-admin="tables.colCreated">Aangemaakt</th>
          <th data-i18n-admin="tables.colExpires">Verloopt</th>
          <th data-i18n-admin="tables.colToken">Token</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table></div>
    </section>"""


def password_resets_table(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """
        SELECT r.*, u.email, u.username
        FROM password_resets r
        JOIN users u ON u.id = r.user_id
        WHERE r.expires_at >= ?
        ORDER BY r.created_at DESC
        """,
        (utc_now_iso(),),
    ).fetchall()
    body = ""
    for row in rows:
        who = row["username"] or row["email"]
        code = row["code"] or "—"
        search = f"{who} {row['email']}".lower()
        body += f"""<tr data-search="{html.escape(search)}">
          <td>{html.escape(str(who))}</td>
          <td>{html.escape(row["email"])}</td>
          <td class="mono">{html.escape(str(code))}</td>
          <td>{fmt_time(row["created_at"])}</td>
          <td>{fmt_time(row["expires_at"])}</td>
        </tr>"""
    if not body:
        body = '<tr><td colspan="5" data-i18n-admin="tables.resetsEmpty">Geen open wachtwoord-resets</td></tr>'
    return f"""
    <section id="resets">
      <h2><span data-i18n-admin="tables.resetsTitle">Open wachtwoord-resets</span> ({len(rows)})</h2>
      <div class="table-wrap"><table>
        <thead><tr>
          <th data-i18n-admin="tables.colUser">Gebruiker</th>
          <th data-i18n-admin="tables.colEmail">E-mail</th>
          <th data-i18n-admin="tables.colCode">Code</th>
          <th data-i18n-admin="tables.colCreated">Aangemaakt</th>
          <th data-i18n-admin="tables.colExpires">Verloopt</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table></div>
    </section>"""


def oauth_states_table(conn: sqlite3.Connection, *, writable: bool = True) -> str:
    rows = conn.execute(
        """
        SELECT state, lang, created_at, expires_at
        FROM oauth_states
        WHERE expires_at >= ?
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (utc_now_iso(),),
    ).fetchall()
    body = ""
    for row in rows:
        search = f"{row['state'][:8]} {row['lang']}".lower()
        body += f"""<tr data-search="{html.escape(search)}">
          <td class="mono">{html.escape(row["state"][:10])}…</td>
          <td>{html.escape(row["lang"])}</td>
          <td>{fmt_time(row["created_at"])}</td>
          <td>{fmt_time(row["expires_at"])}</td>
        </tr>"""
    if not body:
        body = '<tr><td colspan="4" data-i18n-admin="tables.oauthEmpty">Geen actieve OAuth-states</td></tr>'
    purge_btn = (
        action_form(
            "purge_oauth",
            {},
            "Verlopen opschonen",
            "btn--ghost",
            confirm_key="actions.purgeExpired",
        )
        if writable
        else ""
    )
    return f"""
    <section id="oauth">
      <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.65rem;">
        <h2 style="margin:0;"><span data-i18n-admin="tables.oauthTitle">Google OAuth-states</span> ({len(rows)})</h2>
        {purge_btn}
      </div>
      <div class="table-wrap"><table>
        <thead><tr>
          <th data-i18n-admin="tables.colState">State</th>
          <th data-i18n-admin="tables.colLanguage">Taal</th>
          <th data-i18n-admin="tables.colCreated">Aangemaakt</th>
          <th data-i18n-admin="tables.colExpires">Verloopt</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table></div>
    </section>"""


def dashboard_page(
    conn: sqlite3.Connection,
    db_path: str,
    flash: str = "",
    session: dict[str, Any] | None = None,
) -> str:
    session = session or {}
    writable = can_write_admin(session)
    moderate = can_moderate_admin(session)
    stats = collect_stats(conn)
    now = fmt_time(utc_now_iso())
    flash_html = admin_flash_html(flash)
    owner_tools = ""
    if is_owner_session(session):
        owner_tools = """
      <a class="btn btn--ghost" href="/admin/export/users.csv" data-i18n-admin="dashboard.exportUsers">Export gebruikers</a>
      <a class="btn btn--ghost" href="/admin/export/plans.csv" data-i18n-admin="dashboard.exportPlans">Export racks</a>
      <a class="btn btn--ghost" href="/admin/export/sessions.csv" data-i18n-admin="dashboard.exportSessions">Export sessies</a>
      <a class="btn btn--ghost" href="/admin/export/full.json" data-i18n-admin="dashboard.exportAll">Export alles (JSON)</a>"""
    body = f"""
    {admin_topbar(session, "RackForge Panel", "Databasebeheer", title_key="dashboard.title", subtitle_key="dbManagement")}
    <p class="sub" style="margin:-0.75rem 0 1rem;">{html.escape(now)}</p>
    {admin_nav(session, "panel")}
    {flash_html}
    <div class="toolbar">
      <input type="search" id="admin-search" data-i18n-admin-attr="placeholder"
        data-i18n-admin="dashboard.search" placeholder="Zoeken (naam, e-mail, ID…)">
      {owner_tools}
    </div>
    <div class="stats">
      <div class="stat"><div class="stat__n">{stats["users"]}</div><div class="stat__l" data-i18n-admin="dashboard.statsUsers">Gebruikers</div></div>
      <div class="stat"><div class="stat__n">{stats["new_7d"]}</div><div class="stat__l" data-i18n-admin="dashboard.statsNew7d">Nieuw (7d)</div></div>
      <div class="stat"><div class="stat__n">{stats["new_30d"]}</div><div class="stat__l" data-i18n-admin="dashboard.statsNew30d">Nieuw (30d)</div></div>
      <div class="stat"><div class="stat__n">{stats["active_7d"]}</div><div class="stat__l" data-i18n-admin="dashboard.statsActive7d">Actief (7d)</div></div>
      <div class="stat"><div class="stat__n">{stats["sessions"]}</div><div class="stat__l" data-i18n-admin="dashboard.statsSessions">Sessies nu</div></div>
      <div class="stat"><div class="stat__n">{stats["plans"]}</div><div class="stat__l" data-i18n-admin="dashboard.statsPlans">Rack-plannen</div></div>
      <div class="stat"><div class="stat__n">{stats["google"]}</div><div class="stat__l" data-i18n-admin="dashboard.statsGoogle">Google</div></div>
      <div class="stat"><div class="stat__n">{stats["blocked"]}</div><div class="stat__l" data-i18n-admin="dashboard.statsBlocked">Geblokkeerd</div></div>
      <div class="stat"><div class="stat__n">{stats["pending_verify"]}</div><div class="stat__l" data-i18n-admin="dashboard.statsVerify">Verificaties</div></div>
      <div class="stat"><div class="stat__n">{stats["pending_reset"]}</div><div class="stat__l" data-i18n-admin="dashboard.statsResets">Resets</div></div>
    </div>
    <section>
      <h2 data-i18n-admin="dashboard.registrations">Registraties per dag (14 dagen)</h2>
      {weekly_chart(conn)}
    </section>
    <p class="sub"><span data-i18n-admin="tables.dbLabel">DB</span>: <span class="mono">{html.escape(db_path)}</span></p>
    {users_table(conn, writable=writable, moderate=moderate)}
    {plans_table(conn, writable=writable)}
    {sessions_table(conn, writable=writable, moderate=moderate)}
    {verifications_table(conn)}
    {password_resets_table(conn)}
    {oauth_states_table(conn, writable=writable)}
    """
    return page_shell(
        "Dashboard", body, with_js=True, page_title_key="nav.dashboard"
    )


def parse_form_body(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8", errors="replace")
    data: dict[str, str] = {}
    for part in raw.split("&"):
        if "=" in part:
            key, value = part.split("=", 1)
            data[unquote_plus(key)] = unquote_plus(value)
    return data


def send_html_response(handler: BaseHTTPRequestHandler, status: int, html_text: str) -> None:
    body = html_text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("X-Robots-Tag", "noindex, nofollow")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_download(handler: BaseHTTPRequestHandler, filename: str, content: str, mime: str) -> None:
    body = content.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def admin_delete_user(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM email_verifications WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM plans WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    remove_avatar_files(user_id)


def count_superadmins(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) AS n FROM admin_users WHERE role = 'superadmin'"
        ).fetchone()["n"]
    )


def count_owners(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) AS n FROM admin_users WHERE role = 'owner'"
        ).fetchone()["n"]
    )


def handle_admin_action(
    conn: sqlite3.Connection, form: dict[str, str], session: dict[str, Any]
) -> str:
    action = form.get("action", "")
    writable = can_write_admin(session)
    moderate = can_moderate_admin(session)
    manage_admins = can_manage_admin_users(session)
    moderate_actions = {"toggle_block", "revoke_session"}
    write_actions = {"delete_user", "delete_plan", "purge_oauth"}

    if action in ADMIN_USER_ACTIONS:
        if not manage_admins:
            return "flash.noAdminRights"
    elif action in moderate_actions:
        if not moderate:
            return "flash.noPermission"
    elif action in write_actions or action:
        if not writable:
            return "flash.noPermission"

    if action == "create_admin_user":
        username = form.get("username", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        role, role_err = resolve_create_admin_role(session, form.get("role", ""))
        if role_err:
            return role_err
        if not ADMIN_USERNAME_RE.match(username):
            return "flash.invalidUsername"
        if not email:
            return "flash.emailRequired"
        if not ADMIN_EMAIL_RE.match(email):
            return "flash.invalidEmail"
        if not password:
            return "flash.passwordRequired"
        if not role:
            return "flash.invalidRole"
        exists = conn.execute(
            "SELECT 1 FROM admin_users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
        if exists:
            return "flash.usernameExists"
        email_taken = conn.execute(
            "SELECT 1 FROM admin_users WHERE email = ? COLLATE NOCASE", (email,)
        ).fetchone()
        if email_taken:
            return "flash.emailExists"
        require_password_change = form.get("require_password_change") == "1"
        salt, digest = hash_admin_password(password)
        admin_id = secrets.token_hex(16)
        conn.execute(
            """
            INSERT INTO admin_users (
                id, username, password_salt, password_hash, role, created_at, app_user_id,
                must_change_password, email
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                admin_id,
                username,
                salt,
                digest,
                role,
                utc_now_iso(),
                1 if require_password_change else 0,
                email,
            ),
        )
        conn.commit()
        return json.dumps(
            {"k": "flash.adminAdded", "v": {"username": username, "roleKey": role}}
        )

    if action == "update_admin_role":
        if not can_change_admin_roles(session):
            return "flash.onlyOwnerSuperChangeRoles"
        admin_id = form.get("admin_id", "")
        role, role_err = resolve_assignable_admin_role(session, form.get("role", ""))
        if role_err:
            return role_err
        if not re.fullmatch(r"[a-f0-9]{32}", admin_id or ""):
            return "flash.invalidAdminId"
        if not role:
            return "flash.invalidRole"
        row = conn.execute(
            "SELECT id, role FROM admin_users WHERE id = ?", (admin_id,)
        ).fetchone()
        if not row:
            return "flash.adminNotFound"
        current_role = normalize_admin_role(row["role"]) or row["role"]
        if not can_edit_admin_target(session, current_role):
            return "flash.noEditAdminRights"
        if current_role == "owner" and role != "owner" and count_owners(conn) <= 1:
            return "flash.cannotDemoteLastOwner"
        if (
            current_role == "superadmin"
            and role != "superadmin"
            and count_superadmins(conn) <= 1
            and not is_owner_session(session)
        ):
            return "flash.cannotDemoteLastSuperadmin"
        conn.execute("UPDATE admin_users SET role = ? WHERE id = ?", (role, admin_id))
        if session.get("admin_id") == admin_id:
            session["role"] = role
        conn.commit()
        return json.dumps(
            {"k": "flash.roleUpdated", "v": {"roleKey": role}}
        )

    if action == "delete_admin_user":
        admin_id = form.get("admin_id", "")
        if not re.fullmatch(r"[a-f0-9]{32}", admin_id or ""):
            return "flash.invalidAdminId"
        if session.get("admin_id") == admin_id:
            return "flash.cannotDeleteSelf"
        row = conn.execute(
            "SELECT role FROM admin_users WHERE id = ?", (admin_id,)
        ).fetchone()
        if not row:
            return "flash.adminNotFound"
        current_role = normalize_admin_role(row["role"]) or row["role"]
        if not can_delete_admin_target(session, current_role):
            return "flash.noDeleteAdminRights"
        if current_role == "owner" and count_owners(conn) <= 1:
            return "flash.cannotDeleteLastOwner"
        if (
            current_role == "superadmin"
            and count_superadmins(conn) <= 1
            and not is_owner_session(session)
        ):
            return "flash.cannotDeleteLastSuperadmin"
        conn.execute("DELETE FROM admin_users WHERE id = ?", (admin_id,))
        conn.commit()
        return "flash.adminDeleted"

    if action == "require_admin_password_reset":
        admin_id = form.get("admin_id", "")
        password = form.get("password", "")
        if not re.fullmatch(r"[a-f0-9]{32}", admin_id or ""):
            return "flash.invalidAdminId"
        if session.get("admin_id") == admin_id:
            return "flash.cannotResetSelfPassword"
        if not password:
            return "flash.passwordRequired"
        row = conn.execute(
            "SELECT username, role FROM admin_users WHERE id = ?", (admin_id,)
        ).fetchone()
        if not row:
            return "flash.adminNotFound"
        current_role = normalize_admin_role(row["role"]) or row["role"]
        if not can_reset_admin_password(session, current_role):
            return "flash.noResetPasswordRights"
        salt, digest = hash_admin_password(password)
        conn.execute(
            """
            UPDATE admin_users
            SET password_salt = ?, password_hash = ?, must_change_password = 1
            WHERE id = ?
            """,
            (salt, digest, admin_id),
        )
        conn.commit()
        return json.dumps(
            {
                "k": "flash.passwordResetRequired",
                "v": {"username": row["username"]},
            }
        )

    if action == "delete_user":
        user_id = form.get("user_id", "")
        if not ID_RE.match(user_id):
            return "flash.invalidUserId"
        admin_delete_user(conn, user_id)
        conn.commit()
        return "flash.userDeleted"
    if action == "toggle_block":
        user_id = form.get("user_id", "")
        if not ID_RE.match(user_id):
            return "flash.invalidUserId"
        row = conn.execute("SELECT blocked FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return "flash.userNotFound"
        new_val = 0 if row["blocked"] else 1
        conn.execute("UPDATE users SET blocked = ? WHERE id = ?", (new_val, user_id))
        if new_val:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()
        return "flash.userUnblocked" if not new_val else "flash.userBlocked"
    if action == "revoke_session":
        token = form.get("token", "")
        if not re_fullmatch_hex64(token):
            return "flash.invalidSession"
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return "flash.sessionRevoked"
    if action == "delete_plan":
        plan_id = form.get("plan_id", "")
        if not ID_RE.match(plan_id):
            return "flash.invalidPlanId"
        conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
        conn.commit()
        return "flash.planDeleted"
    if action == "purge_oauth":
        conn.execute("DELETE FROM oauth_states WHERE expires_at < ?", (utc_now_iso(),))
        conn.execute(
            "DELETE FROM email_verifications WHERE expires_at < ?", (utc_now_iso(),)
        )
        conn.execute("DELETE FROM password_resets WHERE expires_at < ?", (utc_now_iso(),))
        conn.commit()
        return "flash.purged"
    return "flash.unknownAction"


def export_users_csv(conn: sqlite3.Connection) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "id",
            "username",
            "email",
            "email_verified",
            "google",
            "password_set",
            "blocked",
            "lang",
            "created_at",
        ]
    )
    for row in conn.execute(
        """
        SELECT id, username, email, email_verified, google_id IS NOT NULL AS google,
               password_set, blocked, lang, created_at
        FROM users ORDER BY created_at DESC
        """
    ):
        writer.writerow(
            [
                row["id"],
                row["username"],
                row["email"],
                row["email_verified"],
                row["google"],
                row["password_set"],
                row["blocked"],
                row["lang"],
                row["created_at"],
            ]
        )
    return out.getvalue()


def export_plans_csv(conn: sqlite3.Connection) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["id", "user_id", "rack_height", "device_count", "updated_at", "created_at"]
    )
    for row in conn.execute(
        "SELECT id, user_id, rack_height, devices, updated_at, created_at FROM plans"
    ):
        try:
            count = len(json.loads(row["devices"]))
        except (TypeError, json.JSONDecodeError):
            count = 0
        writer.writerow(
            [
                row["id"],
                row["user_id"],
                row["rack_height"],
                count,
                row["updated_at"],
                row["created_at"],
            ]
        )
    return out.getvalue()


def export_sessions_csv(conn: sqlite3.Connection) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["token_prefix", "user_id", "email", "username", "created_at", "expires_at"])
    for row in conn.execute(
        """
        SELECT substr(s.token, 1, 8) AS tp, s.user_id, u.email, u.username,
               s.created_at, s.expires_at
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        ORDER BY s.created_at DESC
        """
    ):
        writer.writerow(
            [
                row["tp"],
                row["user_id"],
                row["email"],
                row["username"],
                row["created_at"],
                row["expires_at"],
            ]
        )
    return out.getvalue()


def export_full_json(conn: sqlite3.Connection) -> str:
    data: dict[str, Any] = {
        "exportedAt": utc_now_iso(),
        "stats": collect_stats(conn),
        "users": [],
        "plans": [],
        "sessions": [],
        "emailVerifications": [],
        "passwordResets": [],
    }
    for row in conn.execute("SELECT * FROM users"):
        item = dict(row)
        item.pop("password_salt", None)
        item.pop("password_hash", None)
        data["users"].append(item)
    for row in conn.execute("SELECT * FROM plans"):
        item = dict(row)
        try:
            item["devices"] = json.loads(item["devices"])
        except (TypeError, json.JSONDecodeError):
            pass
        data["plans"].append(item)
    for row in conn.execute(
        """
        SELECT substr(s.token,1,8) AS tokenPrefix, s.user_id, s.created_at, s.expires_at,
               u.email, u.username
        FROM sessions s JOIN users u ON u.id = s.user_id
        """
    ):
        data["sessions"].append(dict(row))
    for row in conn.execute("SELECT * FROM email_verifications"):
        data["emailVerifications"].append(dict(row))
    for row in conn.execute(
        "SELECT user_id, code, created_at, expires_at FROM password_resets"
    ):
        data["passwordResets"].append(dict(row))
    return json.dumps(data, indent=2, ensure_ascii=False)


def handle_admin_get(handler: BaseHTTPRequestHandler, path: str, db_path: str) -> bool:
    if not path.startswith("/admin"):
        return False

    if path in ("/admin", "/admin/"):
        session = get_admin_session(handler)
        if session:
            qs = parse_qs(urlparse(handler.path).query)
            legacy_msg = qs.get("msg", [""])[0]
            if legacy_msg:
                token = get_admin_token(handler)
                if token:
                    set_admin_flash(token, legacy_msg)
            admin_redirect(handler, admin_post_login_path(session))
        else:
            admin_redirect(handler, ADMIN_LOGIN_PATH)
        return True

    if path == ADMIN_FORGOT_PATH:
        session = get_admin_session(handler)
        if session:
            admin_redirect(handler, admin_post_login_path(session))
            return True
        send_html_response(handler, 200, forgot_password_request_page())
        return True

    if path == ADMIN_FORGOT_VERIFY_PATH:
        admin_redirect(handler, ADMIN_FORGOT_PATH)
        return True

    if path == ADMIN_RESET_PATH:
        session = get_admin_session(handler)
        if session:
            admin_redirect(handler, admin_post_login_path(session))
            return True
        qs = parse_qs(urlparse(handler.path).query)
        token = (qs.get("token", [""])[0] or "").strip()
        if not ADMIN_RESET_TOKEN_RE.match(token):
            send_html_response(
                handler, 400, admin_reset_password_page("", "flash.invalidResetToken")
            )
            return True
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            ensure_admin_schema(conn)
            purge_expired_admin_password_resets(conn)
            row = conn.execute(
                """
                SELECT 1 FROM admin_password_resets
                WHERE token = ? AND expires_at >= ?
                """,
                (token, utc_now_iso()),
            ).fetchone()
        if not row:
            send_html_response(
                handler, 400, admin_reset_password_page("", "flash.invalidResetToken")
            )
            return True
        send_html_response(handler, 200, admin_reset_password_page(token))
        return True

    if path == ADMIN_LOGIN_PATH:
        session = get_admin_session(handler)
        if session:
            admin_redirect(handler, admin_post_login_path(session))
            return True
        qs = parse_qs(urlparse(handler.path).query)
        reset_ok = qs.get("reset", [""])[0] == "ok"
        with sqlite3.connect(db_path) as conn:
            available = admin_login_available(conn)
        send_html_response(
            handler, 200, login_page(available=available, reset_ok=reset_ok)
        )
        return True

    if path == ADMIN_CHANGE_PASSWORD_PATH:
        session = get_admin_session(handler)
        if not session:
            admin_redirect(handler, ADMIN_LOGIN_PATH)
            return True
        voluntary = not session.get("must_change_password")
        send_html_response(handler, 200, change_password_page(voluntary=voluntary))
        return True

    if path == ADMIN_PANEL_PATH:
        session = get_admin_session(handler)
        if not session:
            admin_redirect(handler, ADMIN_LOGIN_PATH)
            return True
        if require_admin_password_changed(handler, session, path):
            return True
        flash = admin_panel_flash(handler)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            ensure_admin_schema(conn)
            session = sync_env_admin_session(conn, session)
            page = dashboard_page(conn, db_path, flash=flash, session=session)
        send_html_response(handler, 200, page)
        return True

    if path == ADMIN_USERS_PATH:
        session = get_admin_session(handler)
        if not session:
            admin_redirect(handler, ADMIN_LOGIN_PATH)
            return True
        if require_admin_password_changed(handler, session, path):
            return True
        if not can_manage_admin_users(session):
            token = get_admin_token(handler)
            if token:
                store_admin_flash(token, "flash.noAdminRights")
            admin_redirect(handler, ADMIN_PANEL_PATH)
            return True
        flash = admin_panel_flash(handler)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            ensure_admin_schema(conn)
            session = sync_env_admin_session(conn, session)
            page = admin_users_page(conn, flash=flash, session=session)
        send_html_response(handler, 200, page)
        return True

    if not admin_authenticated(handler):
        admin_redirect(handler, ADMIN_LOGIN_PATH)
        return True

    exports = {
        "/admin/export/users.csv": ("rackforge-users.csv", export_users_csv, "text/csv"),
        "/admin/export/plans.csv": ("rackforge-plans.csv", export_plans_csv, "text/csv"),
        "/admin/export/sessions.csv": (
            "rackforge-sessions.csv",
            export_sessions_csv,
            "text/csv",
        ),
        "/admin/export/full.json": (
            "rackforge-export.json",
            export_full_json,
            "application/json",
        ),
    }
    if path in exports:
        session = get_admin_session(handler)
        if not session or not is_owner_session(session):
            admin_redirect(handler, ADMIN_PANEL_PATH)
            return True
        filename, fn, mime = exports[path]
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            content = fn(conn)
        send_download(handler, filename, content, mime)
        return True

    return False


def handle_admin_post(handler: BaseHTTPRequestHandler, path: str, db_path: str) -> bool:
    if not path.startswith("/admin"):
        return False

    if path == ADMIN_FORGOT_PATH:
        form = parse_form_body(handler)
        username = form.get("username", "").strip()
        if not ADMIN_USERNAME_RE.match(username):
            send_html_response(
                handler, 400, forgot_password_request_page("flash.forgotUserNotFound")
            )
            return True
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            ensure_admin_schema(conn)
            row = conn.execute(
                """
                SELECT id, username FROM admin_users
                WHERE username = ? COLLATE NOCASE
                """,
                (username,),
            ).fetchone()
            if not row:
                send_html_response(
                    handler, 404, forgot_password_request_page("flash.forgotUserNotFound")
                )
                return True
            mail = resolve_admin_reset_email(conn, row["id"], row["username"])
            if not mail:
                send_html_response(
                    handler, 400, forgot_password_request_page("flash.noResetEmail")
                )
                return True
            if not smtp_configured():
                send_html_response(
                    handler,
                    503,
                    forgot_password_request_page("flash.smtpNotConfigured"),
                )
                return True
            to_email, lang = mail
            _token, code = create_admin_password_reset(conn, row["id"])
            conn.commit()
            try:
                send_admin_password_reset_email(to_email, code, lang)
            except Exception as exc:
                print(f"[{utc_now_iso()}] Admin reset email failed: {exc}")
                send_html_response(
                    handler,
                    503,
                    forgot_password_request_page("flash.resetEmailFailed"),
                )
                return True
        send_html_response(
            handler,
            200,
            forgot_password_verify_page(
                row["username"],
                mask_email(to_email),
                ok_key="forgotPassword.codeSent",
            ),
        )
        return True

    if path == ADMIN_FORGOT_VERIFY_PATH:
        form = parse_form_body(handler)
        username = form.get("username", "").strip()
        code = normalize_admin_reset_code(form.get("code", ""))
        if not ADMIN_USERNAME_RE.match(username):
            send_html_response(
                handler, 400, forgot_password_request_page("flash.forgotUserNotFound")
            )
            return True
        if not ADMIN_RESET_CODE_RE.match(code):
            send_html_response(
                handler,
                400,
                forgot_password_verify_page(
                    username,
                    mask_email(""),
                    error_key="flash.invalidResetCode",
                ),
            )
            return True
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            ensure_admin_schema(conn)
            purge_expired_admin_password_resets(conn)
            admin_row = conn.execute(
                """
                SELECT id FROM admin_users
                WHERE username = ? COLLATE NOCASE
                """,
                (username,),
            ).fetchone()
            if not admin_row:
                send_html_response(
                    handler, 400, forgot_password_request_page("flash.forgotUserNotFound")
                )
                return True
            reset_row = conn.execute(
                """
                SELECT token FROM admin_password_resets
                WHERE admin_id = ? AND code = ? AND expires_at >= ?
                """,
                (admin_row["id"], code, utc_now_iso()),
            ).fetchone()
            if not reset_row:
                mail = resolve_admin_reset_email(conn, admin_row["id"], username)
                masked = mask_email(mail[0]) if mail else ""
                send_html_response(
                    handler,
                    400,
                    forgot_password_verify_page(
                        username,
                        masked,
                        error_key="flash.invalidResetCode",
                    ),
                )
                return True
        admin_redirect(
            handler, f"{ADMIN_RESET_PATH}?token={quote(reset_row['token'])}"
        )
        return True

    if path == ADMIN_RESET_PATH:
        form = parse_form_body(handler)
        token = form.get("token", "").strip()
        password = form.get("password", "")
        confirm = form.get("password_confirm", "")
        if not ADMIN_RESET_TOKEN_RE.match(token):
            send_html_response(
                handler, 400, admin_reset_password_page("", "flash.invalidResetToken")
            )
            return True
        if not password:
            send_html_response(
                handler,
                400,
                admin_reset_password_page(token, "flash.passwordRequired"),
            )
            return True
        if password != confirm:
            send_html_response(
                handler,
                400,
                admin_reset_password_page(token, "changePassword.passwordMismatch"),
            )
            return True
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            ensure_admin_schema(conn)
            purge_expired_admin_password_resets(conn)
            row = conn.execute(
                """
                SELECT admin_id FROM admin_password_resets
                WHERE token = ? AND expires_at >= ?
                """,
                (token, utc_now_iso()),
            ).fetchone()
            if not row:
                send_html_response(
                    handler,
                    400,
                    admin_reset_password_page("", "flash.invalidResetToken"),
                )
                return True
            salt, digest = hash_admin_password(password)
            conn.execute(
                """
                UPDATE admin_users
                SET password_salt = ?, password_hash = ?, must_change_password = 0
                WHERE id = ?
                """,
                (salt, digest, row["admin_id"]),
            )
            conn.execute(
                "DELETE FROM admin_password_resets WHERE admin_id = ?", (row["admin_id"],)
            )
            conn.commit()
        admin_redirect(handler, f"{ADMIN_LOGIN_PATH}?reset=ok")
        return True

    if path == "/admin/login":
        form = parse_form_body(handler)
        username = form.get("username", "").strip()
        password = form.get("password", "")
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            if not admin_login_available(conn):
                send_html_response(
                    handler, 503, login_page("Admin niet geconfigureerd", available=False)
                )
                return True
            login = resolve_admin_login(conn, username, password)
        if not login:
            send_html_response(
                handler, 401, login_page("Onjuist gebruikersnaam of wachtwoord", available=True)
            )
            return True
        admin_id, display_name, role, must_change_password = login
        token = create_admin_session(
            admin_id=admin_id,
            username=display_name,
            role=role,
            must_change_password=must_change_password,
        )
        handler.send_response(302)
        handler.send_header(
            "Location",
            ADMIN_CHANGE_PASSWORD_PATH if must_change_password else ADMIN_PANEL_PATH,
        )
        handler.send_header("Set-Cookie", admin_cookie_header(token))
        handler.end_headers()
        return True

    if path == "/admin/logout":
        token = get_admin_token(handler)
        if token:
            ADMIN_SESSIONS.pop(token, None)
            ADMIN_FLASH.pop(token, None)
        handler.send_response(302)
        handler.send_header("Location", ADMIN_LOGIN_PATH)
        handler.send_header("Set-Cookie", clear_admin_cookie_header())
        handler.end_headers()
        return True

    if path == ADMIN_CHANGE_PASSWORD_PATH:
        session = get_admin_session(handler)
        if not session:
            admin_redirect(handler, ADMIN_LOGIN_PATH)
            return True
        voluntary = not session.get("must_change_password")
        form = parse_form_body(handler)
        current_password = form.get("current_password", "")
        password = form.get("password", "")
        confirm = form.get("password_confirm", "")

        def change_password_error(key: str, status: int = 400) -> None:
            send_html_response(
                handler, status, change_password_page(key, voluntary=voluntary)
            )

        if voluntary and not current_password:
            change_password_error("flash.passwordRequired")
            return True
        if not password:
            change_password_error("flash.passwordRequired")
            return True
        if password != confirm:
            change_password_error("changePassword.passwordMismatch")
            return True
        admin_id = session.get("admin_id")
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            ensure_admin_schema(conn)
            session = sync_env_admin_session(conn, session)
            admin_id = session.get("admin_id")
            if voluntary:
                if not verify_session_admin_password(conn, session, current_password):
                    change_password_error("flash.wrongCurrentPassword")
                    return True
            if admin_id:
                salt, digest = hash_admin_password(password)
                conn.execute(
                    """
                    UPDATE admin_users
                    SET password_salt = ?, password_hash = ?, must_change_password = 0
                    WHERE id = ?
                    """,
                    (salt, digest, admin_id),
                )
                conn.commit()
        session["must_change_password"] = False
        if voluntary:
            token = get_admin_token(handler)
            if token:
                set_admin_flash(token, "flash.passwordUpdated")
        admin_redirect(handler, ADMIN_PANEL_PATH)
        return True

    if not admin_authenticated(handler):
        admin_redirect(handler, ADMIN_LOGIN_PATH)
        return True

    if path == "/admin/action":
        session = get_admin_session(handler)
        if not session:
            admin_redirect(handler, ADMIN_LOGIN_PATH)
            return True
        if require_admin_password_changed(handler, session, path):
            return True
        form = parse_form_body(handler)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            ensure_admin_schema(conn)
            msg = handle_admin_action(conn, form, session)
        token = get_admin_token(handler)
        if token:
            store_admin_flash(token, msg)
        admin_redirect(handler, admin_action_return_to(form, form.get("action", "")))
        return True

    return False