"""
Weather operations using Open-Meteo API (No key required)
"""
import requests
import urllib.parse
import json
import datetime

def get_current_weather(location_name="Tokyo"):
    """
    Get current weather and forecast for a specific location.
    Returns structured data about temperature, weather conditions, etc.
    """
    try:
        # 1. Geocoding
        # Default to Tokyo if location is vague
        if not location_name: location_name = "Tokyo"
        
        search_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location_name)}&count=1&language=ja&format=json"
        geo_res = requests.get(search_url).json()
        
        if not geo_res.get('results'):
            return {"error": f"場所が見つかりませんでした: {location_name}"}
        
        location = geo_res['results'][0]
        lat = location['latitude']
        lon = location['longitude']
        name = location['name']
        
        # 2. Weather Forecast
        # Request current weather and daily max/min for clothing advice
        weather_url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                       "&current=temperature_2m,apparent_temperature,precipitation,weather_code"
                       "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
                       "&timezone=auto&forecast_days=1")
        
        w_res = requests.get(weather_url).json()
        
        if w_res.get('error'):
            return {"error": "天気情報の取得に失敗しました"}
            
        current = w_res.get('current', {})
        daily = w_res.get('daily', {})
        
        # Helper to decode WMO code
        def get_weather_label(code):
            # Simple WMO code map
            if code == 0: return "快晴"
            if code in [1, 2, 3]: return "晴れ時々曇り"
            if code in [45, 48]: return "霧"
            if code in [51, 53, 55]: return "霧雨"
            if code in [61, 63, 65]: return "雨"
            if code in [80, 81, 82]: return "にわか雨"
            if code in [71, 73, 75, 77]: return "雪"
            if code in [95, 96, 99]: return "雷雨"
            return "不明"

        return {
            "location": name,
            "current": {
                "temp": current.get('temperature_2m'),
                "feels_like": current.get('apparent_temperature'),
                "condition": get_weather_label(current.get('weather_code')),
                "precipitation": current.get('precipitation')
            },
            "today_forecast": {
                "max_temp": daily.get('temperature_2m_max', [None])[0],
                "min_temp": daily.get('temperature_2m_min', [None])[0],
                "pop": daily.get('precipitation_probability_max', [None])[0],
                "condition": get_weather_label(daily.get('weather_code', [0])[0])
            }
        }
        
    except Exception as e:
        return {"error": f"天気取得エラー: {str(e)}"}
