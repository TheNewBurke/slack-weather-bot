import requests
import slack

# this token should be an environmental variable, but I placed it here for simplicity
SLACK_TOKEN = "xoxb-563006611778-875462649778-E9fov9F92w0vUXVTam7yGjkr"
GPS_COORDS = "40.7128,-74.0060"
DARKSKY_API_KEY = "636fe1e20ddfcb4878a0ea3685b1ac29"
rtmclient = slack.RTMClient(token=SLACK_TOKEN)
webclient = slack.WebClient(token=SLACK_TOKEN)

# using this to store mutable variables to access within functions
_mutables = {
    'channel': None,
    'text': None,
    'thread_ts': None,
    'user': None,
    'tomorrow_morning': None,
    'conditions': None,
    'message_queued': False
}


def check_for_weather_change():
    daily_data = _mutables['conditions']['daily']['data']
    text = None
    today = daily_data[0]
    tomorrow = daily_data[1]

    if tomorrow['temperatureHigh'] >= (today['temperatureHigh'] + 10):
        text = "Tomorrow's hottest promises to be much warmer than today, dress accordingly"
    if tomorrow['temperatureLow'] <= (today['temperatureLow'] - 10):
        text += " Tomorrow's coldest promises to be much cooler than today, dress accordingly"
    if text is not None:
        send_message_for_tomorrow_morning(text)


def send_message_for_tomorrow_morning(text):
    resp = webclient.chat_scheduleMessage(
        text=text,
        channel=_mutables['channel'],
        post_at=_mutables['tomorrow_morning']
    )
    print(f"message scheduled and response was {resp}")
    _mutables['message_queued'] = False


def compare_morning_times():
    # we get conditions once, when we start, until we get a new day
    # this is to reduce the number of calls arising from incoming messages
    if _mutables['conditions'] is None:
        _mutables['conditions'] = get_current_conditions()
    tomorrow = _mutables['conditions']['daily']['data'][1]
    if 'sunriseTime' in tomorrow:

        # if acquired conditions hold a tomorrow morning time
        # > the existing tomorrow morning time, update that times in _mutables store as we have a new day
        # this will queue a message to be sent for the morning if the conditions dictate that
        if _mutables['tomorrow_morning'] is not None and tomorrow['sunriseTime'] > _mutables['tomorrow_morning']:
            _mutables['tomorrow_morning'] = tomorrow['sunriseTime']
            _mutables['conditions'] = get_current_conditions()
            _mutables['message_queued'] = True
        elif _mutables['tomorrow_morning'] is None:
            _mutables['tomorrow_morning'] = tomorrow['sunriseTime']
            _mutables['message_queued'] = True
        else:
            pass


def get_current_conditions():
    api_conditions_url = "https://api.darksky.net/forecast/" + DARKSKY_API_KEY + "/" + GPS_COORDS + "?units=auto"
    resp = requests.get(api_conditions_url)
    condition_json = resp.json()
    return condition_json


def slack_daily_weather_response(data, which_day):
    if which_day == "today":
        day = _mutables['conditions']['daily']['data'][0]
        response_text = f"""
The weather is currently {day['summary']}
The temperature is between {day['temperatureLow']} and {day['temperatureHigh']},
There is a {day['precipProbability']}% chance of {day['precipType']}
with winds up to {day['windGust']} mph
"""
    elif which_day == "tomorrow":
        day = _mutables['conditions']['daily']['data'][1]
        response_text = f"""
The weather tomorrow will be {day['summary']}
The temperature will be between {day['temperatureLow']} and {day['temperatureHigh']},
There will be a {day['precipProbability']}% chance of {day['precipType']}
with winds up to {day['windGust']} mph
"""
    else:
        pass
    _mutables['channel'] = data['channel']
    _mutables['thread_ts'] = data['ts']
    _mutables['user'] = data['user']

    webclient.chat_postMessage(
        channel=_mutables['channel'],
        text=response_text,
        thread_ts=_mutables['thread_ts'],
        user=_mutables['user']
    )


# acquires messages from the channel and evaluates applicability
@slack.RTMClient.run_on(event='message')
def slackbot_input(**payload):
    data = payload['data']
    if 'text' in data:
        compare_morning_times()
        if 'Weather now' in data['text']:
            slack_daily_weather_response(data, "today")
        if 'Weather tomorrow' in data['text']:
            slack_daily_weather_response(data, "tomorrow")
        if _mutables['message_queued']:
            check_for_weather_change()


rtmclient.start()
