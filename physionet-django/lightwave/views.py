import os
import re
import shutil
import subprocess

from django.conf import settings
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from project.views import project_auth


# public_root: chroot directory for public databases
if settings.STATIC_ROOT:
    public_root = settings.STATIC_ROOT
else:
    public_root = os.path.join(settings.BASE_DIR, 'static')

# public_dbpath: path to main database directory within public_root
public_dbpath = '/physiobank/database'

# dbcal_file: absolute path to the wfdbcal file
dbcal_file = public_root + public_dbpath + '/wfdbcal'

# Kludge for testing
if not os.path.exists(public_root + public_dbpath + '/DBS'):
    _default_dblist = 'udb\tExample WFDB record'
else:
    _default_dblist = None


def lightwave_home(request):
    """
    Render LightWAVE main page for published databases.
    """
    return render(request, 'lightwave/home.html', {
        'lightwave_server_url': reverse('lightwave_server'),

        # FIXME: Scribe should be updated to save annotations to
        # logged-in user's account.  And probably we should just
        # disable editing for non-logged-in users, and tell them to
        # log in if they want to edit.

        'lightwave_scribe_url':
        'https://archive.physionet.org/cgi-bin/lw-scribe',
    })


@project_auth(auth_mode=2)
def lightwave_project_home(request, project_slug, project, **kwargs):
    """
    Render LightWAVE main page for an active project.
    """
    # FIXME: Show an error message if no RECORDS file is present.
    return render(request, 'lightwave/home.html', {
        'lightwave_server_url': reverse('lightwave_project_server',
                                        args=(project_slug,)),

        # FIXME: As above, need an updated scribe and a place to save
        # annotations.

        'lightwave_scribe_url': '',
    })


_lightwave_command = (shutil.which('sandboxed-lightwave'),)
_cgi_header = re.compile('(?ia)(Content-Type):\s*(.*)')


def serve_lightwave(query_string, root, dbpath='/', dblist=None, dbcal=None,
                    public=False):
    """
    Request data from the LightWAVE server.

    The server is sandboxed so that it can only access files within
    the given root directory.  By default, the root directory is also
    used as the default database path, but a different path (or
    multiple paths, separated by spaces) can be specified as dbpath.
    These paths must be accessible within the sandbox root directory.

    The list of available databases is retrieved from the DBS file by
    default; this can be overridden by specifying dblist.

    The global wfdbcal file is used by default, but can be overridden
    by specifying dbcal.  (Unlike dbpath, this path is not relative to
    the sandbox root.)

    If public is true, the data may be accessed by any web page,
    either using XMLHttpRequest or using JSONP.  If public is false,
    the data may be accessed only by same-origin pages.
    """

    # This function implements an extremely basic subset of CGI - just
    # enough to be compatible with lightwave.  In particular: none of
    # the CGI variables other than QUERY_STRING are provided, and only
    # the Content-Type header is supported.

    env = {
        'WFDB': dbpath,
        'LIGHTWAVE_ROOT': root,
        'QUERY_STRING': query_string,
        'LIGHTWAVE_WFDBCAL': (dbcal or dbcal_file),
    }
    if dblist:
        env['LIGHTWAVE_DBLIST'] = dblist

    resp = HttpResponse()
    if public:
        resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Headers'] = 'x-requested-with'
    else:
        env['LIGHTWAVE_DISABLE_JSONP'] = '1'

    with subprocess.Popen(_lightwave_command, close_fds=True, env=env,
                          stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE) as proc:
        for line in proc.stdout:
            line = line.rstrip(b'\n\r').decode()
            if line == '':
                break
            m = _cgi_header.match(line)
            if m:
                resp[m.group(1)] = m.group(2)
        else:
            raise Exception('no response header')
        resp.write(proc.stdout.read())
    return resp


def lightwave_server(request):
    """
    Request LightWAVE data for a published database.
    """
    return serve_lightwave(query_string=request.GET.urlencode(),
                           root=public_root,
                           dbpath=public_dbpath,
                           dblist=_default_dblist,
                           public=True)


@project_auth(auth_mode=2)
def lightwave_project_server(request, project_slug, project, **kwargs):
    """
    Request LightWAVE data for an active project.
    """
    # Kludge: override the db parameter in the URL, since we are
    # chrooting to project.file_root(), but the client should see each
    # project as a distinct database for annotation purposes
    return serve_lightwave(query_string=('db=.&' + request.GET.urlencode()),
                           root=project.file_root(),
                           dblist=(project_slug + '\t' + project.title),
                           public=False)


def lightwave_js(request, file_name, **kwargs):
    """
    Request LightWAVE static JavaScript files.
    """
    return redirect(static(os.path.join('lightwave/js', file_name)))


def lightwave_css(request, file_name, **kwargs):
    """
    Request LightWAVE static CSS files.
    """
    return redirect(static(os.path.join('lightwave/css', file_name)))


def lightwave_doc(request, file_name, **kwargs):
    """
    Request LightWAVE static documentation files.
    """
    return redirect(static(os.path.join('lightwave/doc', file_name)))
