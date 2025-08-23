from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Flush database with deferred constraints'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute('SET CONSTRAINTS ALL DEFERRED')
            flush_sql = self.get_flush_sql()
            for sql in flush_sql:
                cursor.execute(sql)
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.stdout.write(self.style.SUCCESS('Database flushed successfully'))

    def get_flush_sql(self):
        from django.core.management import call_command
        from io import StringIO
        output = StringIO()
        call_command('sqlflush', stdout=output)
        output.seek(0)
        return output.read().splitlines()