CREATE TABLE IF NOT EXISTS weather_forecasts (
    forecast_id BIGSERIAL PRIMARY KEY,
    
    -- Location Metadata (Repeated per row in a single table)
    latitude NUMERIC(8, 5) NOT NULL,
    longitude NUMERIC(8, 5) NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    elevation NUMERIC(5, 1),                 -- Optional, often provided by Open-Meteo
    
    -- Timestamp
    forecast_time TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Temperature Fields
    temperature_2m NUMERIC(4, 1),           -- °C or °F
    apparent_temperature NUMERIC(4, 1),     -- "Feels like"
    dew_point_2m NUMERIC(4, 1),
    
    -- Moisture & Precipitation
    relative_humidity_2m SMALLINT,          -- Percentage (0-100)
    rain NUMERIC(5, 2),                      -- mm
    precipitation_probability SMALLINT,     -- Percentage (0-100)
    
    -- Atmosphere & Environment
    surface_pressure NUMERIC(6, 1),          -- hPa
    cloud_cover SMALLINT,                   -- Percentage (0-100)
    visibility NUMERIC(7, 1),                -- meters
    uv_index NUMERIC(3, 1),
    
    -- Wind Dynamics
    wind_speed_10m NUMERIC(5, 1),            -- km/h or m/s
    wind_direction_10m SMALLINT,            -- Degrees (0-360)
    wind_gusts_10m NUMERIC(5, 1),
    
    -- Sun & Day Indicators
    sunshine_duration NUMERIC(6, 1),         -- Seconds
    is_day BOOLEAN,                          -- Converted from 1/0 to boolean
    
    -- Ingestion Metadata
    model_used VARCHAR(50) DEFAULT 'best_match',
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraint to prevent duplicate records for the same spot at the same time
    CONSTRAINT unique_lat_lon_time UNIQUE (latitude, longitude, forecast_time)
);

-- Optimization Indexes for Single-Table Queries
CREATE INDEX IF NOT EXISTS idx_weather_time ON weather_forecasts (forecast_time DESC);
CREATE INDEX IF NOT EXISTS idx_weather_geo_time ON weather_forecasts (latitude, longitude, forecast_time DESC);