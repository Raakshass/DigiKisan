"""
KisanMitra AI — Open-Meteo Weather Fetcher
=============================================
Fetches agricultural weather data from Open-Meteo API (100% free, no API key).

Data fetched per state:
- 7-day forecast: temperature, humidity, precipitation, wind
- Soil conditions: soil temperature, soil moisture at multiple depths
- Agricultural indicators: evapotranspiration, sunshine duration
- Historical comparison: last 30 days vs normal

Source: https://api.open-meteo.com/v1/forecast
Docs:   https://open-meteo.com/en/docs

Free tier: Unlimited for non-commercial use, 10,000 req/day commercial.
We make ~5 requests per monthly run (one per state) — well within limits.

Output:
- One IngestedDocument per state with 7-day agricultural weather summary
- Tagged with state, category="weather_advisory"
"""
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import httpx

from app.services.data_ingestion.base_source import DataSource, IngestedDocument
from app.core.state_mappings import STATE_CONFIG, get_state_config


class OpenMeteoFetcher(DataSource):
    """
    Fetches free weather data from Open-Meteo API for agricultural advisory.

    No API key required. Uses latitude/longitude from state_mappings.
    """

    name = "open_meteo"
    category = "weather_advisory"
    refresh_interval_days = 7   # Weekly refresh (weather changes fast)
    max_docs_per_state = 1      # One summary doc per state
    request_timeout = 15
    request_delay = 0.5         # Open-Meteo is fast, light delay

    _BASE_URL = "https://api.open-meteo.com/v1/forecast"

    # Weather variables relevant to agriculture
    _DAILY_VARS = [
        "temperature_2m_max",
        "temperature_2m_min",
        "apparent_temperature_max",
        "apparent_temperature_min",
        "precipitation_sum",
        "rain_sum",
        "precipitation_probability_max",
        "wind_speed_10m_max",
        "et0_fao_evapotranspiration",
        "sunshine_duration",
        "uv_index_max",
    ]

    _HOURLY_VARS = [
        "soil_temperature_6cm",
        "soil_temperature_18cm",
        "soil_moisture_3_to_9cm",
        "soil_moisture_9_to_27cm",
        "relative_humidity_2m",
    ]

    async def fetch_documents(self, state: str) -> List[IngestedDocument]:
        """Fetch 7-day agricultural weather forecast for a state."""
        state_cfg = get_state_config(state)
        if not state_cfg:
            print(f"   ❌ Unknown state code: {state}")
            return []

        lat, lon = state_cfg["lat_lon"]
        state_name = state_cfg["full_name"]

        try:
            # Fetch daily forecast + soil data
            daily_data = await self._fetch_daily(lat, lon)
            soil_data = await self._fetch_soil(lat, lon)

            if not daily_data:
                print(f"   ⚠️ No weather data returned for {state_name}")
                return []

            # Build markdown advisory
            markdown = self._build_advisory(
                state_code=state,
                state_name=state_name,
                daily=daily_data,
                soil=soil_data,
                lat=lat,
                lon=lon,
            )

            doc = IngestedDocument(
                content=markdown,
                filename=self.sanitize_filename(
                    f"{state}_weather_advisory_{datetime.now().strftime('%Y_%m')}"
                ),
                state=state,
                district=None,  # State-level advisory
                category=self.category,
                source=self.name,
                metadata={
                    "lat": lat,
                    "lon": lon,
                    "forecast_days": 7,
                    "state_name": state_name,
                },
            )

            print(f"   ✅ Weather advisory: {len(markdown)} chars for {state_name}")
            return [doc]

        except Exception as e:
            print(f"   ❌ Open-Meteo fetch failed for {state_name}: {e}")
            return []

    # -------------------------------------------------------------------
    # API Calls
    # -------------------------------------------------------------------
    async def _fetch_daily(
        self, lat: float, lon: float
    ) -> Optional[Dict[str, Any]]:
        """Fetch 7-day daily forecast."""
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ",".join(self._DAILY_VARS),
            "forecast_days": 7,
            "timezone": "Asia/Kolkata",
        }

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                resp = await client.get(self._BASE_URL, params=params)
                if resp.status_code != 200:
                    print(f"      ⚠️ Open-Meteo daily returned {resp.status_code}")
                    return None
                return resp.json().get("daily")
        except Exception as e:
            print(f"      ❌ Daily fetch error: {e}")
            return None

    async def _fetch_soil(
        self, lat: float, lon: float
    ) -> Optional[Dict[str, Any]]:
        """Fetch soil temperature and moisture data."""
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(self._HOURLY_VARS),
            "forecast_days": 3,  # Soil data: 3 days is enough
            "timezone": "Asia/Kolkata",
        }

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                resp = await client.get(self._BASE_URL, params=params)
                if resp.status_code != 200:
                    return None
                return resp.json().get("hourly")
        except Exception as e:
            print(f"      ℹ️ Soil data unavailable: {e}")
            return None

    # -------------------------------------------------------------------
    # Markdown Builder
    # -------------------------------------------------------------------
    def _build_advisory(
        self,
        state_code: str,
        state_name: str,
        daily: Dict[str, Any],
        soil: Optional[Dict[str, Any]],
        lat: float,
        lon: float,
    ) -> str:
        """Build a comprehensive agricultural weather advisory."""

        header = self.build_document_header(
            title=f"Agricultural Weather Advisory — {state_name}",
            state=state_code,
            source_url=f"https://open-meteo.com/?lat={lat}&lon={lon}",
        )

        sections = []

        # --- 7-Day Forecast Table ---
        sections.append("## 7-Day Weather Forecast\n")
        sections.append(
            "| Date | Max Temp (°C) | Min Temp (°C) | Rain (mm) | "
            "Rain Prob (%) | Wind (km/h) | Sunshine (h) |"
        )
        sections.append("|------|-----------|-----------|---------|-----------|---------|-----------|")

        dates = daily.get("time", [])
        for i, date in enumerate(dates):
            t_max = self._safe_get(daily, "temperature_2m_max", i, "—")
            t_min = self._safe_get(daily, "temperature_2m_min", i, "—")
            rain = self._safe_get(daily, "precipitation_sum", i, "0.0")
            rain_prob = self._safe_get(daily, "precipitation_probability_max", i, "—")
            wind = self._safe_get(daily, "wind_speed_10m_max", i, "—")
            sunshine = self._safe_get(daily, "sunshine_duration", i, "—")

            # Convert sunshine from seconds to hours
            if sunshine != "—":
                try:
                    sunshine = f"{float(sunshine) / 3600:.1f}"
                except (ValueError, TypeError):
                    pass

            sections.append(
                f"| {date} | {t_max} | {t_min} | {rain} | "
                f"{rain_prob} | {wind} | {sunshine} |"
            )

        # --- Agricultural Interpretation ---
        sections.append("\n## Agricultural Impact Assessment\n")

        # Rainfall analysis
        total_rain = sum(
            float(v) for v in (daily.get("precipitation_sum") or [])
            if v is not None
        )
        max_rain_day = max(
            (float(v) for v in (daily.get("precipitation_sum") or []) if v is not None),
            default=0,
        )

        if total_rain > 100:
            sections.append(
                "### ⚠️ Heavy Rainfall Alert\n\n"
                f"Total expected rainfall: **{total_rain:.1f} mm** over 7 days.\n"
                "- **Risk:** Waterlogging, crop damage, fungal infections\n"
                "- **Action:** Ensure field drainage, delay fertilizer application\n"
                "- **Crops at risk:** Low-lying paddy, vegetables, cotton\n"
            )
        elif total_rain > 50:
            sections.append(
                "### 🌧️ Moderate Rainfall Expected\n\n"
                f"Total expected rainfall: **{total_rain:.1f} mm** over 7 days.\n"
                "- Good for kharif crops if monsoon season\n"
                "- Monitor for pest buildup in humid conditions\n"
            )
        elif total_rain < 10:
            sections.append(
                "### ☀️ Dry Spell Warning\n\n"
                f"Total expected rainfall: **{total_rain:.1f} mm** over 7 days.\n"
                "- **Risk:** Moisture stress, wilting\n"
                "- **Action:** Schedule irrigation, apply mulch to conserve moisture\n"
                "- Consider drought-tolerant varieties for new plantings\n"
            )

        # Temperature analysis
        temps_max = [
            float(v) for v in (daily.get("temperature_2m_max") or [])
            if v is not None
        ]
        temps_min = [
            float(v) for v in (daily.get("temperature_2m_min") or [])
            if v is not None
        ]

        if temps_max:
            avg_max = sum(temps_max) / len(temps_max)
            avg_min = sum(temps_min) / len(temps_min) if temps_min else 0

            if avg_max > 42:
                sections.append(
                    "### 🔥 Extreme Heat Alert\n\n"
                    f"Average maximum temperature: **{avg_max:.1f}°C**\n"
                    "- **Risk:** Heat stress on crops, livestock dehydration\n"
                    "- **Action:** Irrigate in early morning/late evening, "
                    "provide shade for livestock\n"
                    "- Avoid transplanting during peak heat\n"
                )
            elif avg_min < 5:
                sections.append(
                    "### ❄️ Cold Wave Alert\n\n"
                    f"Average minimum temperature: **{avg_min:.1f}°C**\n"
                    "- **Risk:** Frost damage to rabi crops\n"
                    "- **Action:** Light irrigation before frost nights, "
                    "use straw mulch\n"
                )

        # Evapotranspiration
        et0_values = [
            float(v) for v in (daily.get("et0_fao_evapotranspiration") or [])
            if v is not None
        ]
        if et0_values:
            avg_et0 = sum(et0_values) / len(et0_values)
            sections.append(
                f"### 💧 Irrigation Advisory\n\n"
                f"Average daily evapotranspiration (ET0): **{avg_et0:.1f} mm/day**\n"
                f"Weekly crop water demand: ~**{avg_et0 * 7:.0f} mm**\n"
                f"- Adjust irrigation to match ET0 for water efficiency\n"
            )

        # --- Soil Conditions ---
        if soil:
            sections.append("## Soil Conditions (3-Day Average)\n")

            soil_temp_6 = self._avg_hourly(soil, "soil_temperature_6cm")
            soil_temp_18 = self._avg_hourly(soil, "soil_temperature_18cm")
            soil_moist_shallow = self._avg_hourly(soil, "soil_moisture_3_to_9cm")
            soil_moist_deep = self._avg_hourly(soil, "soil_moisture_9_to_27cm")

            sections.append(
                f"| Metric | Value |\n"
                f"|--------|-------|\n"
                f"| Soil temp (6 cm) | {soil_temp_6}°C |\n"
                f"| Soil temp (18 cm) | {soil_temp_18}°C |\n"
                f"| Soil moisture (3-9 cm) | {soil_moist_shallow} m³/m³ |\n"
                f"| Soil moisture (9-27 cm) | {soil_moist_deep} m³/m³ |\n"
            )

            # Germination advisory based on soil temp
            if soil_temp_6 != "—":
                try:
                    temp = float(soil_temp_6)
                    if 20 <= temp <= 30:
                        sections.append(
                            "✅ **Soil temperature ideal for germination** "
                            "(most kharif and rabi crops)\n"
                        )
                    elif temp < 15:
                        sections.append(
                            "⚠️ **Soil too cold for germination** — "
                            "delay sowing of warm-season crops\n"
                        )
                    elif temp > 35:
                        sections.append(
                            "⚠️ **Soil too hot** — "
                            "may reduce germination rates, irrigate to cool\n"
                        )
                except ValueError:
                    pass

        # --- Crop-Specific Advisory (based on state's major crops) ---
        state_cfg = get_state_config(state_code)
        if state_cfg:
            crops = state_cfg.get("major_crops", [])
            if crops:
                sections.append(
                    f"## Crop-Specific Notes ({state_name})\n\n"
                    f"Major crops in this state: **{', '.join(crops)}**\n"
                )

                # Season detection
                month = datetime.now().month
                if 6 <= month <= 10:
                    sections.append(
                        "Current season: **Kharif** (monsoon crops)\n"
                        "- Focus on: rice, maize, cotton, soybean, pulses\n"
                        "- Monitor for: stem borer, army worm, blight in humid conditions\n"
                    )
                elif 11 <= month or month <= 3:
                    sections.append(
                        "Current season: **Rabi** (winter crops)\n"
                        "- Focus on: wheat, gram, mustard, potato\n"
                        "- Monitor for: aphids, rust, frost damage\n"
                    )
                else:
                    sections.append(
                        "Current season: **Zaid** (summer crops)\n"
                        "- Focus on: vegetables, watermelon, cucumber, moong\n"
                        "- Monitor for: heat stress, water management\n"
                    )

        return header + "\n".join(sections)

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------
    @staticmethod
    def _safe_get(
        data: Dict, key: str, index: int, default: str = "—"
    ) -> str:
        """Safely get a value from API response arrays."""
        try:
            values = data.get(key, [])
            if values and index < len(values) and values[index] is not None:
                val = values[index]
                if isinstance(val, float):
                    return f"{val:.1f}"
                return str(val)
        except (IndexError, TypeError):
            pass
        return default

    @staticmethod
    def _avg_hourly(data: Dict, key: str) -> str:
        """Calculate average of hourly values."""
        try:
            values = [v for v in (data.get(key) or []) if v is not None]
            if values:
                avg = sum(values) / len(values)
                return f"{avg:.1f}"
        except (TypeError, ValueError):
            pass
        return "—"
