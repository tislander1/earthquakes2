# earthquakes2

- Try using read_data_from_file(output_filename) where output_filename is station_LUTZ_and_neighbors_data.csv.
- This will load a data structure with time series for Communication Hill CA and its 50 closest stations.
- The intended application is to predict a time series, given the other time series.

The data source was JPL's GNSS Time Series, and it was found using the command (found in the documentation folder):
wget -r -nd -np -R "index.html*" -A "*.series" "https://sideshow.jpl.nasa.gov/pub/JPL_GPS_Timeseries/repro2018a/post/point"

This was processed using the process_dataset.py script.

Settings:

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

