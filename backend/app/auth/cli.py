"""Give an existing profile a sign-in account from the command line (V3).

Useful for the seeded demo company, or to recover access to a company whose
director lost their password (there is no reset-by-email yet):

    python -m app.auth.cli --name "Camille Laurent" --email camille@example.com

The password is asked interactively and never echoed.
"""

import argparse
import getpass
import sys

from app.auth.security import MIN_PASSWORD_LENGTH, hash_password, normalize_email
from app.core.entities import UserProfile
from app.database import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True, help="Sign-in email (set on the profile if it has none)")
    parser.add_argument("--name", help="Profile name, when the profile has no email yet")
    args = parser.parse_args()

    email = normalize_email(args.email)
    session = SessionLocal()
    try:
        profile = session.query(UserProfile).filter_by(email=email).first()
        if profile is None and args.name:
            matches = session.query(UserProfile).filter_by(name=args.name).all()
            if len(matches) > 1:
                print(f"Several profiles are named {args.name!r}; give them distinct emails first.", file=sys.stderr)
                return 1
            profile = matches[0] if matches else None
        if profile is None:
            print("No such profile.", file=sys.stderr)
            return 1
        password = getpass.getpass("New password: ")
        if len(password) < MIN_PASSWORD_LENGTH or password != getpass.getpass("Repeat it: "):
            print(f"Passwords differ or are shorter than {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
            return 1
        profile.email = email
        profile.password_hash = hash_password(password)
        profile.invite_token_hash = None
        profile.invite_expires_at = None
        session.commit()
        print(f"{profile.name} can now sign in as {email}.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
