from django.shortcuts  import get_object_or_404
from django.http import JsonResponse
from google.cloud import storage
import json
from .models import Video
from django.contrib.auth.models import User
from datetime import datetime, timedelta
import gpxpy
from django.utils import timezone
from celery.result import AsyncResult
from django.core.files.temp import NamedTemporaryFile
from django.conf import settings
from .tasks import process_and_upload_gpx
from geopy.geocoders import Nominatim
import geopy


bucket_name="bucket-licenta-rovin"
storage_client = storage.Client()

def get_user_id_from_username(username):
    try:
        user = User.objects.get(username=username)
        return user.id
    except User.DoesNotExist:
        return None

def upload_video(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            video_name = data.get('video_name')
            user_id = get_user_id_from_username(username)
            
            if not (video_name.endswith('.mp4') or video_name.endswith('.MP4')):
                return JsonResponse({'success': False, 'message': 'File provided is not an mp4'}, status=404)

            if video_name.endswith('.MP4'):
                video_name = video_name.rsplit('.', 1)[0] + '.mp4'

            if user_id is None:
                return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
            
            if Video.objects.filter(user_profile__user_id=user_id, video_name=video_name).exists():
                return JsonResponse({'success': False, 'message': 'Video name already associated with the user'}, status=404)

            # database creation
            video = Video.objects.create(video_name=video_name, user_profile_id=user_id, timestamp=timezone.now())

            blob = storage_client.bucket(bucket_name).blob(f'uploads/{user_id}/{video_name}')
            current_datetime = datetime.now()
            expiration_time = current_datetime + timedelta(minutes=10)
            signed_url = blob.generate_signed_url(
                version='v4',
                expiration=expiration_time,
                method='PUT',
                content_type='video/mp4'
            )

            return JsonResponse({'success': True, 'signed_url': signed_url}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)

    
def convert_gpx(request):
    if request.method == 'POST':
        try:
            username = request.POST.get('username')

            mp4_file_name = request.POST.get('mp4_file')
            user_id = get_user_id_from_username(username)

            if not mp4_file_name:
                return JsonResponse({'success': False, 'message': 'No MP4 file provided'}, status=400)

            
            process_and_upload_gpx.delay(username, user_id,  mp4_file_name)


            return JsonResponse({'success': True, 'message': 'GPX uploaded to cloud'}, status=202)
    
        
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)

    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


def get_video_by_name(request):

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            video_name = data.get('video_name')
            user_id = get_user_id_from_username(username)

            if not video_name:
                return JsonResponse({'success': False, 'message': 'Missing video_name parameter'}, status=400)

            if user_id is None:
                return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
            
            if video_name.endswith('.MP4'):
                video_name = video_name.rsplit('.', 1)[0] + '.mp4'

            if not Video.objects.filter(user_profile_id=user_id, video_name=video_name).exists():
                return JsonResponse({'success': False, 'message': 'Video name is not associated with the user'}, status=409)
            
            
            video_blob = storage_client.bucket(bucket_name).blob(f'uploads/{user_id}/{video_name}')

            expiration_time = datetime.now() + timedelta(hours=8)
            
            video_signed_url = video_blob.generate_signed_url(
                version='v4',
                expiration=expiration_time,
                method='GET',
                # content_type='video/mp4',
            )
        

            return JsonResponse({
                'success': True,
                'video': video_signed_url,
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)  
    
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)

def display_gpx(request):

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('video_user')
            video_name = data.get('video_name')
            user_id = get_user_id_from_username(username)
            
            gpx_name = video_name.replace('.mp4', '.gpx')

            gpx_blob = storage_client.bucket(bucket_name).blob(f'uploads/{user_id}/{gpx_name}')
            gpx_file = gpx_blob.download_as_string()
     
            gpx = gpxpy.parse(gpx_file)

            waypoints = []
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        waypoints.append({
                        'lat': point.latitude,
                        'lng': point.longitude,
                        'ele': point.elevation,
                        'time': point.time.timestamp()
                    })

            if len(waypoints)<1 :
                return JsonResponse({'success': False, 'message': 'No GPS metadata in video'}, status=400)  
            

            return JsonResponse({'waypoints': waypoints})
        
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)  
    
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


def upload_video_gpx(request):

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            video_name = data.get('video_name')
            user_id = get_user_id_from_username(username)
            
            if not (video_name.endswith('.mp4') or video_name.endswith('.MP4')):
                return JsonResponse({'success': False, 'message': 'File provided is not an mp4'}, status=404)

            if video_name.endswith('.MP4'):
                video_name = video_name.rsplit('.', 1)[0] + '.mp4'

            if user_id is None:
                return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
            
            if Video.objects.filter(user_profile__user_id=user_id, video_name=video_name).exists():
                return JsonResponse({'success': False, 'message': 'Video name already associated with the user'}, status=404)

            # database creation
            video = Video.objects.create(video_name=video_name, user_profile_id=user_id, timestamp=timezone.now())

            video_blob = storage_client.bucket(bucket_name).blob(f'uploads/{user_id}/{video_name}')
            current_datetime = datetime.now()
            expiration_time = current_datetime + timedelta(minutes=10)
            video_url = video_blob.generate_signed_url(
                version='v4',
                expiration=expiration_time,
                method='PUT',
                content_type='video/mp4'
            )
            
            gpx_name = video_name.replace('.mp4', '.gpx')
            
            gpx_blob = storage_client.bucket(bucket_name).blob(f'uploads/{user_id}/{gpx_name}')
            gpx_url= gpx_blob.generate_signed_url(
                version='v4',
                expiration=expiration_time,
                method='PUT',
                content_type = 'application/gpx+xml'
            )



            return JsonResponse({'success': True, 'video_url': video_url, 'gpx_url' : gpx_url}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)
    

def update_city_country(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            video_name = data.get('video_name')
            user_id = get_user_id_from_username(username)
            
            video_name=video_name.replace('.MP4', '.mp4')
            gpx_name = video_name.replace('.mp4', '.gpx')

            gpx_blob = storage_client.bucket(bucket_name).blob(f'uploads/{user_id}/{gpx_name}')
            gpx_file = gpx_blob.download_as_string()
     
            gpx = gpxpy.parse(gpx_file)

            waypoint = None

            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        waypoint = {
                            'lat': point.latitude,
                            'lng': point.longitude,
                            'ele': point.elevation,
                            'time': point.time.timestamp()
                        }
                        break 
                    if waypoint:
                        break
                if waypoint:
                    break

            if waypoint is None :
                return JsonResponse({'success': False, 'message': 'No GPS metadata in video'}, status=400)  

            
            #  find country/ city
            try:
                geolocator = Nominatim(user_agent="MyGeocodingAppVlad")
                location = geolocator.reverse((waypoint['lat'], waypoint['lng']), exactly_one=True)
                address = location.address
                country = location.raw['address']['country']
                city = location.raw['address']['city'] if 'city' in location.raw['address'] else location.raw['address']['town'] if 'town' in location.raw['address'] else location.raw['address']['village']
                # print(f"Address: {address}, City: {city}, Country: {country}")

                # set country/city in DB if not already done
                video, created = Video.objects.get_or_create(video_name=video_name, user_profile__user_id=user_id, defaults={'country': country, 'city': city})
                if not created:
                    if not video.country:
                        video.country = country
                    if not video.city:
                        video.city = city
                    video.save()
                return JsonResponse({'success': True, 'message': 'Updated country and city of the video'}, status=200)
            except geopy.exc.GeocoderInsufficientPrivileges:
                print("Error: Insufficient privileges Geocoder.")
            except Exception as e:
                print(f"An error occurred: {str(e)}")


    
        
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)

    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)
    

def display_city_country(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            video_user = data.get('video_user')
            video_name = data.get('video_name')
            user_id = get_user_id_from_username(video_user)

            video_name=video_name.replace('.MP4', '.mp4')

            video = get_object_or_404(Video, video_name=video_name, user_profile__user_id=user_id)

            # Check if the video has country and city data
            if video.country and video.city:
                return JsonResponse({'success': True, 'country': video.country, 'city': video.city})
            else:
                return JsonResponse({'success': False, 'message': 'Country and city information not available for the video'}, status=404)

        except json.JSONDecodeError:
                return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)

    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)
