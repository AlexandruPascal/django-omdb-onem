import datetime
import jwt
import onem
import requests

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.views.generic import View as _View
from django.shortcuts import get_object_or_404

from .models import History
from .helpers import OmdbMixin


class View(_View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *a, **kw):
        return super(View, self).dispatch(*a, **kw)

    def get_user(self):
        # return User.objects.filter()[0]
        token = self.request.headers.get('Authorization')
        if token is None:
            raise PermissionDenied

        data = jwt.decode(token.replace('Bearer ', ''), key='87654321')
        user, created = User.objects.get_or_create(id=data['sub'],
                                                   username=str(data['sub']))
        return user

    def to_response(self, menu_or_form):
        return HttpResponse(menu_or_form.as_json(),
                            content_type='application/json')


class HomeView(View):
    http_method_names = ['get']

    def get(self, request):
        # user = self.get_user()

        body = [
            onem.menus.MenuItem('Search', url=reverse('search_wizard')),
        ]

        return self.to_response(onem.menus.Menu(body, header='menu'))


class SearchWizardView(View, OmdbMixin):
    http_method_names = ['get', 'post']

    def get(self, request):
        body = [
            onem.forms.FormItem(
                'keyword',
                onem.forms.FormItemType.STRING,
                'Send keywords to search',
                header='search', footer='Send keyword'
            )
        ]
        return self.to_response(
            onem.forms.Form(body, reverse('search_wizard'), method='POST',
                            meta=onem.forms.FormMeta(
                                confirm=False, status=False,
                                status_in_header=False
                            ))
        )

    def post(self, request):
        keyword = request.POST['keyword']
        response = self.get_page_data(keyword)
        if response['Response'] == 'False':
            return self.to_response(onem.menus.Menu(
                [onem.menus.MenuItem('No results', is_option=False)],
                header='{keyword} SEARCH'.format(keyword=keyword.title()),
                footer='Send BACK and search again'
            ))

        body = []
        for result in response['Search']:
            body.append(onem.menus.MenuItem(u'{title} - {year}'.format(
                title=result['Title'], year=result['Year']
            ), url=reverse('movie_detail', args=[result['imdbID']])))

        return self.to_response(onem.menus.Menu(
            body,
            header='{keyword} SEARCH'.format(keyword=keyword.title()),
            footer='Select result'
        ))


class MovieDetailView(View, OmdbMixin):
    http_method_names = ['get', 'post']

    def get(self, request, id):
        response = self.get_page_data(id)
        if response['Response'] == 'False':
            return self.to_response(onem.menus.Menu(
                [onem.menus.MenuItem('Please try again later',
                                     is_option=False)],
                header='{movie_title} INFO'.format(
                    movie_title=response['Title']
                ),
                footer='Send BACK'
            ))

        history = History.objects.create(
            user=self.get_user(),
            omdb_id=response['imdbID'],
            title=response['Title'],
            year=response['Year'],
            rate=response['Ratings'][0]['Value'],
            plot=response['Plot'],
            date=datetime.datetime.now()
        )
        history.save()

        body = [
            onem.forms.FormItem(
                'movie description',
                onem.forms.FormItemType.STRING,
                u'\n'.join([
                    u'Title: {movie_title}'.format(
                        movie_title=response['Title']
                    ),
                    u'Year: {movie_year}'.format(movie_year=response['Year']),
                    u'Rate: {movie_rate}'.format(
                        movie_rate=response['Ratings'][0]['Value']
                    ),
                    u'Plot: {movie_plot}'.format(movie_plot=response['Plot'])
                ]),
                header='Movie details', footer='send BACK to search again')
        ]
        return self.to_response(onem.forms.Form(
            body, reverse('search_wizard'), method='GET',
            meta=onem.forms.FormMeta(
                confirm=False, status=False, status_in_header=False
            )
        ))
