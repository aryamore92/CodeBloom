"""Create a real teacher account using the trusted local command line."""
from getpass import getpass
import sqlite3
import server

if __name__=='__main__':
    server.init_db(seed_demo=False)
    print('\nCreate a CodeBloom teacher account\n')
    name=input('Teacher name: ').strip()
    email=input('Email address: ').strip().lower()
    class_name=input('Classroom name: ').strip()
    password=getpass('Password (at least 8 characters): ')
    confirmation=getpass('Confirm password: ')
    if password!=confirmation: raise SystemExit('Passwords do not match. Run this command again.')
    try:
        code=server.create_teacher(name,email,password,class_name)
        print(f'\nTeacher account created. Classroom code: {code}\nSign in with the email and password you entered.\n')
    except (ValueError,sqlite3.IntegrityError) as e:
        raise SystemExit('Could not create teacher: '+str(e))
