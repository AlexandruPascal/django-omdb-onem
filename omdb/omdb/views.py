import datetime
import jwt
import onem

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
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
        body = [
            onem.menus.MenuItem(label='Search', url=reverse('search_wizard'))
        ]
        user = self.get_user()
        history_count = user.history_set.count()
        if history_count:
            body.append(
                onem.menus.MenuItem(
                    label='History ({count})'.format(count=history_count),
                    url=reverse('history')),
            )
        return self.to_response(onem.menus.Menu(body, header='menu'))


class SearchWizardView(View, OmdbMixin):
    http_method_names = ['get', 'post']

    def get(self, request):
        body = [
            onem.forms.FormItem(
                name='keyword',
                item_type=onem.forms.FormItemType.STRING,
                label='Send keywords to search',
                header='search', footer='Send keyword'
            )
        ]
        return self.to_response(
            onem.forms.Form(body, url=reverse('search_wizard'), method='POST',
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
                [onem.menus.MenuItem(label='No results', is_option=False)],
                header='{keyword} SEARCH'.format(keyword=keyword.title()),
                footer='Send BACK and search again'
            ))

        body = []
        for result in response['Search']:
            body.append(onem.menus.MenuItem(
                label=u'{title} - {year}'.format(
                    title=result['Title'], year=result['Year']
                ),
                url=reverse('movie_detail', args=[result['imdbID']])
            ))

        return self.to_response(onem.menus.Menu(
            body,
            header='{keyword} SEARCH'.format(keyword=keyword.title()),
            footer='Select result'
        ))


class HistoryView(View, OmdbMixin):
    http_method_names = ['get']

    def get(self, requset):
        user = self.get_user()
        history = user.history_set.order_by('-datetime')
        body = []
        for movie in history:
            body.append(onem.menus.MenuItem(
                label=u'{title} - {year}'.format(
                    title=movie.title, year=movie.year
                ),
                url=reverse('movie_detail', args=[movie.omdb_id])
            ))

        return self.to_response(onem.menus.Menu(
            body, header='history', footer='Select from history'
        ))


class MovieDetailView(View, OmdbMixin):
    http_method_names = ['get', 'post']

    def get(self, request, id):
        history = History.objects.all()
        if not any([movie for movie in history if movie.omdb_id == id]):
            response = self.get_page_data(id)
            if response['Response'] == 'False':
                return self.to_response(onem.menus.Menu(
                    [onem.menus.MenuItem(label='Please try again later',
                                         is_option=False)],
                    header='INFO', footer='Send BACK'
                ))
            omdb_id = response['imdbID']
            title = response['Title']
            year = response['Year']
            rate = response['Ratings'][0]['Value']
            plot = response['Plot']
        else:
            movie_from_history = [
                movie for movie in history if movie.omdb_id == id
            ][0]
            omdb_id = movie_from_history.omdb_id
            title = movie_from_history.title
            year = movie_from_history.year
            rate = movie_from_history.rate
            plot = movie_from_history.plot

        user = self.get_user()
        user_history = user.history_set.all()
        if not any([movie for movie in user_history if movie.omdb_id == id]):
            history_movie = History.objects.create(
                user=self.get_user(), omdb_id=omdb_id, title=title, year=year,
                rate=rate, plot=plot, datetime=datetime.datetime.now()
            )
            history_movie.save()
        else:
            movie_from_user = [
                movie for movie in user_history if movie.omdb_id == id
            ][0]
            movie_from_user.datetime = datetime.datetime.now()
            movie_from_user.save()

        body = [
            onem.forms.FormItem(
                name='movie description',
                item_type=onem.forms.FormItemType.STRING,
                label=u'\n'.join([
                    u'Title: {movie_title}'.format(movie_title=title),
                    u'Year: {movie_year}'.format(movie_year=year),
                    u'Rate: {movie_rate}'.format(movie_rate=rate),
                    u'Plot: {movie_plot}'.format(movie_plot=plot),
                ]),
                header='Movie details', footer='send BACK')
        ]
        return self.to_response(onem.forms.Form(
            body, url=reverse('search_wizard'), method='GET',
            meta=onem.forms.FormMeta(
                confirm=False, status=False, status_in_header=False
            )
        ))
