# script 0

import os
import pandas as pd
import reverse_geocode
from datetime import datetime

# The purpose of this script is to process the raw earthquake data files from the USGS
# and create cleaned, processed files for each station.


# import station_locations_and_velocities_long_lat.txt as two pandas dataframes while ignoring the first column.
# the even rows are position data, the odd rows are velocity data.
# columns are station name, pos/vel, north, east, vertical, north_sigma, east_sigma, vertical_sigma

# source: https://sideshow.jpl.nasa.gov/post/tables/table2.html


# Ignoring the height, find the distance between two locations given latitudes and longitudes using Haversine formula
def haversine_distance(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2

    R = 6371.0  # Earth radius in kilometers

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c
    return distance

def write_data_to_file(data, filename):
    # dump the station and neighbor data to a human readable CSV based format
    with open(filename, mode='w', newline='') as f:
        main_station = data['station_name']
        f.write(f'Main Station: {main_station}\n')
        for station, station_info in data.items():
            if station == 'station_name':
                continue
            f.write(f'\nStation: {station}\n')
            f.write(f'Distance (km): {station_info["distance"]:.2f}\n')
            f.write(f'Latitude, Longitude: {station_info["lat_long"][0]:.6f}, {station_info["lat_long"][1]:.6f}\n')
            f.write(f'Nearest City: {station_info["city"]}\n')
            f.write('Data:\n')
            # on Windows, need to set line_terminator to '\n' to avoid extra blank lines
            station_info['data'].to_csv(f, index=False)
    print(f'Station and neighbor data dumped to file: {filename}')

def read_data_from_file(filename):
    # read the station and neighbor data from the human readable CSV based format
    data = {}
    with open(filename, 'r') as f:
        lines = f.readlines()
        main_station_line = lines[0].strip()
        main_station = main_station_line.split(': ')[1]
        data['station_name'] = main_station
        i = 1
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('Station:'):
                station = line.split(': ')[1]
                i += 1
                distance_line = lines[i].strip()
                distance = float(distance_line.split(': ')[1])
                i += 1
                lat_long_line = lines[i].strip()
                lat_long_str = lat_long_line.split(': ')[1]
                lat_str, long_str = lat_long_str.split(', ')
                lat = float(lat_str)
                long = float(long_str)
                i += 1
                city_line = lines[i].strip()
                city = city_line.split(': ')[1]
                i += 1  # skip 'Data:' line
                i += 1
                data_lines = []
                while i < len(lines) and not lines[i].strip().startswith('Station:'):
                    data_lines.append(lines[i])
                    i += 1
                from io import StringIO
                station_data_df = pd.read_csv(StringIO(''.join(data_lines)))
                data[station] = {'distance': distance,
                                 'lat_long': (lat, long),
                                 'city': city,
                                 'data': station_data_df}
            else:
                i += 1
    print(f'Station and neighbor data read from file: {filename}')
    return data

def find_closest_station(station_positions, lat, long):
    min_distance = float('inf')
    closest_station = None
    for i, row in station_positions.iterrows():
        station_lat = row['North (deg)']
        station_lon = row['East (deg)']
        distance = haversine_distance(lat, long, station_lat, station_lon)
        if distance < min_distance:
            min_distance = distance
            closest_station = row['Station']
    return closest_station

def load_station_data(station_table_version='v1.0', file_path="station_locations_and_velocities.txt"):
    # load the station locations and velocities file into two pandas dataframes
    # even rows are positions, odd rows are velocities
    # output: two dataframes, one for positions, one for velocities

    table2 = pd.read_table(file_path, sep='\s+', header=None, skiprows=1)

    station_positions = table2.iloc[::2]
    station_velocities = table2.iloc[1::2]
    station_positions.columns = ['Station', 'Type', 'North (deg)', 'East (deg)', 'Vertical (mm)',
                        'North_sigma (mm)', 'East_sigma (mm)', 'Vertical_sigma (mm)']
    station_velocities.columns = ['Station', 'Type', 'North_vel (mm/yr)', 'East_vel (mm/yr)', 'Vertical_vel (mm/yr)',
                            'North_vel_sigma (mm/yr)', 'East_vel_sigma (mm/yr)', 'Vertical_vel_sigma (mm/yr)']
    
    # for the station positions, create a new column called 'Nearest stations' that contains the names
    # of the nearest stations within 100 km.
    station_positions['Nearest_Stations'] = ''
    station_positions['Nearest_Station_Distances_km'] = ''
    for i, row in station_positions.iterrows():
        print(f'Finding nearest stations for {row["Station"]} ({i+1} of {len(station_positions)})')
        lat1 = row['North (deg)']
        lon1 = row['East (deg)']
        nearest_stations = []
        nearest_station_distances = []
        for j, other_row in station_positions.iterrows():
            if i == j:
                continue
            lat2 = other_row['North (deg)']
            lon2 = other_row['East (deg)']
            distance = haversine_distance(lat1, lon1, lat2, lon2)
            if distance <= 1000:  # within 1000 km
                nearest_stations.append(other_row['Station'])
                nearest_station_distances.append(distance)
        # sort the nearest stations and nearest station distances by distance
        sorted_stations_with_distances = sorted(zip(nearest_stations, nearest_station_distances), key=lambda x: x[1])
        nearest_stations = [station for station, dist in sorted_stations_with_distances]
        nearest_station_distances = [dist for station, dist in sorted_stations_with_distances]

        station_positions.at[i, 'Nearest_Stations'] = ', '.join(nearest_stations)
        station_positions.at[i, 'Nearest_Station_Distances_km'] = ', '.join([f"{dist:.2f}" for dist in nearest_station_distances])
        x = 2

    # add a table version column and set to version variable
    station_positions['Version'] = station_table_version
    station_velocities['Version'] = station_table_version

    # for each row, find the nearest city by online lookup using North (deg) and East (deg) with reverse_geocode package
    coordinates = list(zip(station_positions['North (deg)'], station_positions['East (deg)']))
    nearest_cities_and_states = reverse_geocode.search(coordinates)
    # if there is a state, save as 'city, state, country' format.  if not save as city, country
    station_positions['Nearest_City'] = [place['city']+', '+place.get('state','') + ', '+place['country'] for place in nearest_cities_and_states]
    station_velocities['Nearest_City'] = [place['city']+', '+place.get('state','') + ', '+place['country'] for place in nearest_cities_and_states]
    # save the city name in a new column called 'Nearest_City'
    return station_positions, station_velocities

def process_files_from_earthquake_database(filenames, unprocessed_file_directory, only_process_the_first_file_in_database=False):
    if only_process_the_first_file_in_database:
        filenames = [filenames[0]]  # only process the first file

    for filename in filenames:
        station = filename.split('.')[0]

        table1 = pd.read_table(unprocessed_file_directory + '/' + filename, sep='\s+')
        table1.columns = ['Decimal_Year',
                        'East (m)', 'North (m)', 'Vertical (m)',
                        'East_sigma (m)', 'North_sigma (m)', 'Vertical_sigma (m)',
                        'E_N_corr', 'E_V_corr', 'N_V_corr',
                        'Time (sec past J2000)',
                        'year', 'month', 'day', 'hour', 'minute', 'second']
        # drop columns we don't need
        # table1 = table1.drop(columns=['Time (sec past J2000)', 'Time_Year', 'Time_MM', 'Time_DD', 'Time_HR', 'Time_MN', 'Time_SS'])

        # Find the day of the year for each Year.decimal entry.
        table1['Station'] = station

        # given Time_Year, Time_MM, Time_DD, Time_HR, we want to find the closest day at noon to each entry,
        # and then find the difference in days (which should be an integer) between that and the epoch (Jan 17, 1994).
        # do this with a lambda function and apply to the whole column.
        epoch = datetime(1994, 1, 17, 12)  # epoch date
        table1['Days_Since_Epoch'] = 0
        def calculate_days_since_epoch(row):
            date = datetime(int(row['year']), int(row['month']), int(row['day']), int(row['hour']))
            delta = date - epoch
            return round(delta.days + delta.seconds / 86400.0)  # include fractional days
        table1['Days_Since_Epoch'] = table1.apply(calculate_days_since_epoch, axis=1)

        # create a new column called 'OOPS'.  This will be set to '' if everything is ok, or an error message if there is an error in the data.
        # For now, just set to ''.
        table1['OOPS'] = ''
        # If the days since epoch is not 1 greater than the previous row, set OOPS to 'Time jump detected'.
        for i in range(1, len(table1)):
            if table1.loc[i, 'Days_Since_Epoch'] != table1.loc[i-1, 'Days_Since_Epoch'] + 1:
                table1.loc[i, 'OOPS'] = 'Time jump detected'
        # We need to check if the Time jump detected can be corrected by linear interpolation.
        # Only allow jumps of 1 day to be corrected.
        for i in range(1, len(table1)-1):
            if table1.loc[i, 'OOPS'] == 'Time jump detected':
                if table1.loc[i, 'Days_Since_Epoch'] - table1.loc[i-1, 'Days_Since_Epoch'] == 2:
                    # we can correct this by linear interpolation.
                    # insert a new row at index i with the average of the previous and next rows.
                    # averaging should be done for the East, North, Vertical and sigma columns.
                    new_row = {}
                    new_row['East (m)'] = (table1.loc[i-1, 'East (m)'] + table1.loc[i, 'East (m)']) / 2
                    new_row['North (m)'] = (table1.loc[i-1, 'North (m)'] + table1.loc[i, 'North (m)']) / 2
                    new_row['Vertical (m)'] = (table1.loc[i-1, 'Vertical (m)'] + table1.loc[i, 'Vertical (m)']) / 2
                    new_row['East_sigma (m)'] = (table1.loc[i-1, 'East_sigma (m)'] + table1.loc[i, 'East_sigma (m)']) / 2
                    new_row['North_sigma (m)'] = (table1.loc[i-1, 'North_sigma (m)'] + table1.loc[i, 'North_sigma (m)']) / 2
                    new_row['Vertical_sigma (m)'] = (table1.loc[i-1, 'Vertical_sigma (m)'] + table1.loc[i, 'Vertical_sigma (m)']) / 2
                    new_row['Days_Since_Epoch'] = table1.loc[i-1, 'Days_Since_Epoch'] + 1
                    new_row['Station'] = table1.loc[i-1, 'Station']
                    table1 = pd.concat([table1.iloc[:i], pd.DataFrame([new_row]), table1.iloc[i:]]).reset_index(drop=True)
                    table1.loc[i+1, 'OOPS'] = ''  # clear the OOPS message
                    table1.loc[i,'OOPS'] = 'Interpolated missing day'
        
        # We want to check if the Time jump detected is caused by repeated entries.  If so, check
        # which one is closest to noon, and keep that one, deleting the others.
        # We want to record the OOPS message as 'Removed duplicate entries'.
        # Once corrected, we need to ensure that we move the index back to before the issue, and that our while loop
        # is guaranteed to terminate correctly.
        i = 1
        while i < len(table1):
            if table1.loc[i, 'OOPS'] == 'Time jump detected':
                current_day = table1.loc[i, 'Days_Since_Epoch']
                duplicate_indices = [i]
                j = i + 1
                while j < len(table1) and table1.loc[j, 'Days_Since_Epoch'] == current_day:
                    duplicate_indices.append(j)
                    j += 1
                if len(duplicate_indices) > 1:
                    # find the index of the entry closest to noon (12:00)
                    closest_index = duplicate_indices[0]
                    closest_time_diff = abs((int(table1.loc[closest_index, 'hour']) + int(table1.loc[closest_index, 'minute'])/60) - 12)
                    for idx in duplicate_indices[1:]:
                        time_diff = abs((int(table1.loc[idx, 'hour']) + int(table1.loc[idx, 'minute'])/60) - 12)
                        if time_diff < closest_time_diff:
                            closest_index = idx
                            closest_time_diff = time_diff
                    # drop all other duplicates except the closest_index
                    for idx in duplicate_indices:
                        if idx != closest_index:
                            table1 = table1.drop(idx)
                    table1 = table1.reset_index(drop=True)
                    table1.loc[closest_index, 'OOPS'] = 'Removed duplicate entries'
                    i = max(1, closest_index - 1)  # move back to before the issue
                else:
                    i += 1
            else:
                i += 1  

        # create a new directory called 'edited' if it doesn't exist
        if not os.path.exists('edited'):
            os.makedirs('edited')

        table1.to_csv('edited/processed_'+filename +'.csv', index=False)
        x = 2
        print(f'Finished processing file: {filename}')
    x = 2

def collect_single_station_and_neighbor_data(station_name, station_positions, processed_data_directory='edited', number_of_neighbors=-1, nearest_within_km=1000):

    # get the Nearest_Stations,Nearest_Station_Distances_km for the given station from station_positions dataframe
    station_row = station_positions[station_positions['Station'] == station_name]
    if station_row.empty:
        raise ValueError(f'Station {station_name} not found in station positions data.')
    nearest_stations = station_row['Nearest_Stations'].values[0].split(', ')
    nearest_station_distances = [float(dist) for dist in station_row['Nearest_Station_Distances_km'].values[0].split(', ')]

    # get longitude and latitude of the station
    station_lat = station_row['North (deg)'].values[0]
    station_lon = station_row['East (deg)'].values[0]

    # filter nearest stations based on nearest_within_km
    filtered_stations = []
    dist_dict = {station_name: 0.0} | dict(zip(nearest_stations, nearest_station_distances))
    lat_long_dict = {station_name: (station_lat, station_lon)}
    city_dict = {station_name: station_row['Nearest_City'].values[0]}

    for station, distance in dist_dict.items():
        if distance <= nearest_within_km:
            filtered_stations.append(station)
            x = 2
            # collect latitude and longitude of the neighbor station
            neighbor_row = station_positions[station_positions['Station'] == station]
            neighbor_lat = neighbor_row['North (deg)'].values[0]
            neighbor_lon = neighbor_row['East (deg)'].values[0]
            neighbor_city = neighbor_row['Nearest_City'].values[0]
            lat_long_dict[station] = (neighbor_lat, neighbor_lon)
            city_dict[station] = neighbor_city

    if number_of_neighbors > 0:
        filtered_stations = filtered_stations[:number_of_neighbors]
    # additionally, ensure the main station is included
    if station_name not in filtered_stations:
        filtered_stations.insert(0, station_name)

    neighbor_data = {'station_name': station_name}
    for neighbor in filtered_stations:
        neighbor_file_path = f'{processed_data_directory}/processed_{neighbor}.series.csv'
        if os.path.exists(neighbor_file_path):
            neighbor_table = pd.read_csv(neighbor_file_path)
            neighbor_data[neighbor] = {'distance': dist_dict[neighbor],
                                       'lat_long': lat_long_dict[neighbor],
                                        'city': city_dict[neighbor],
                                       'data': neighbor_table[['Days_Since_Epoch', 'Decimal_Year',
                                                      'East (m)', 'North (m)', 'Vertical (m)',
                                                      'OOPS']]}
        else:
            print(f'Processed file for neighbor station {neighbor} does not exist.')

    return  neighbor_data

def get_consistent_timebase_with_NaNs(station_neighbor_data):
    # the timebase is defined by the min and max Days_Since_Epoch from the main station
    main_station = station_neighbor_data['station_name']
    main_station_data = station_neighbor_data[main_station]['data']
    min_day = main_station_data['Days_Since_Epoch'].min()
    max_day = main_station_data['Days_Since_Epoch'].max()
    consistent_timebase = list(range(int(min_day), int(max_day)+1))
    # for each station, reindex the data to the consistent timebase, filling missing days with NaN
    for station, station_info in station_neighbor_data.items():
        if station == 'station_name':
            continue
        station_data = station_info['data']
        station_data_reindexed = pd.DataFrame({'Days_Since_Epoch': consistent_timebase})
        station_data_reindexed = station_data_reindexed.merge(station_data, on='Days_Since_Epoch', how='left')
        station_neighbor_data[station]['data'] = station_data_reindexed
    return station_neighbor_data

if __name__ == "__main__":
    station_table_ver = 'v1.1' # version of the station locations and velocities table to use.
                            # If you change this, you need to re-download the station data file and re-process it.
    only_process_the_first_file_in_database = False # for testing purposes, only process the first file in the earthquake database
    process_files_in_database = False   # set to True to process all files in the earthquake database

    get_station_neighbor_data = True        # set to True to collect data for a single station and its neighbors
    get_station_by_lat_long = False         # set to True to find the closest station to the given lat/long.
                                            # If False, use station_to_collect variable.

    dump_neighbor_data_to_file = True       # set to True to dump the collected station and neighbor data to a file
                                            # the file will be named station_[station_name]_and_neighbors_data.csv
    read_neighbor_data_from_file = True    # set to True to read the station and neighbor data back from file   


    lat = 37.3382       # if get_station_by_lat_long is True, specify the latitude here
    long = -121.8863
    station_to_collect = 'LUTZ' # if get_station_by_lat_long is False, specify the station name here
    max_neighbors_to_collect = 50

    station_table_file_path = "station_locations_and_velocities.txt"
    # check if 'station_positions_'+station_table_ver+'.csv' exists.  If it does not, load the station data from the text file.
    if not os.path.exists('station_positions_'+station_table_ver+'.csv'):
        print('Loading station data...')
        station_positions, station_velocities = load_station_data(station_table_ver, station_table_file_path)
        print('Finished loading station data.')

        # save station positions and velocities to csv files
        station_positions.to_csv('station_positions_'+station_table_ver+'.csv', index=False)
        station_velocities.to_csv('station_velocities_'+station_table_ver+'.csv', index=False)
    else:
        print('Station data CSV files already exist. Skipping loading station data from text file.')

    # read in all .series files from earthquake_data directory

    if process_files_in_database:
        unprocessed_file_directory = "earthquake_data"
        filenames = [f for f in os.listdir(unprocessed_file_directory) if '.series' in f]
        print('Processing earthquake data files...')
        process_files_from_earthquake_database(filenames, unprocessed_file_directory, only_process_the_first_file_in_database)
        print('Finished processing all files.')
    else:
        print('Processing of earthquake data files is disabled. Set process_files_in_database = True to enable.')

    if get_station_neighbor_data:
        # find the closest station to specified lat long
        print(f'Collecting data for station {station_to_collect} and its neighbors...')

        station_positions = pd.read_csv('station_positions_'+station_table_ver+'.csv')

        if get_station_by_lat_long:
            print(f'Finding closest station to lat: {lat}, long: {long}...')
            station_to_collect = find_closest_station(station_positions, lat, long)
            print(f'Closest station is {station_to_collect}.')
        else:
            print(f'Using specified station: {station_to_collect}.')
            station_to_collect = station_to_collect # already specified

        station_neighbor_data_original_timebase = collect_single_station_and_neighbor_data(station_to_collect, station_positions, processed_data_directory='edited', number_of_neighbors=max_neighbors_to_collect, nearest_within_km=1000)
        station_neighbor_data_consistent_timebase_with_NaNs = get_consistent_timebase_with_NaNs(station_neighbor_data_original_timebase)
        print(f'Finished collecting data for station {station_to_collect} and its neighbors.')

        if dump_neighbor_data_to_file:
            # let's encode this in a human readable CSV based format before saving.
            # for the dataframes, we want them to be readable, so let's keep data rows together.
            # we should be able to keep a row on a single line, and then have the next row on the next line.
            # it must be easy to read, and we will also need to add a function to read this data back in.
            output_filename = f'station_{station_to_collect}_and_neighbors_data.csv'
            write_data_to_file(station_neighbor_data_consistent_timebase_with_NaNs, output_filename)

    else:
        print('Collection of station neighbor data is disabled. Set get_station_neighbor_data = True to enable.')

    if read_neighbor_data_from_file:
        print('Reading station and neighbor data back from file...')
        output_filename = f'station_{station_to_collect}_and_neighbors_data.csv'
        data_read_back_in = read_data_from_file(output_filename)
        x = 2

    print('All processing complete.')
    x = 2

                        