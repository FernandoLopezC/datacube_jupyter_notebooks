import sys
sys.path.append("/workspace/DQTools/")

import matplotlib
matplotlib.use('nbagg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import ipywidgets as widgets
from pyproj import Proj, transform

from IPython.display import display, clear_output
from IPython.lib.display import FileLink

import helpers.helpers as helpers
from DQTools.dataset import Dataset


class PeatHelpers(helpers.Helpers):

    def get_dates(self, dataset, start, end):
        start = np.datetime64(start)
        end = np.datetime64(end)
        dataset.calculate_timesteps()
        timesteps = dataset.timesteps
        first = self.closest_later_date(timesteps, start)
        last = self.closest_earlier_date(timesteps, end)
        if start != first and first is not None:
            print(f'First available date {first}')
        if end != last and last is not None:
            print(f'Last available date {last}')
        if first is None or last is None:
            print(f'Available dates are {dataset.first_timestep} to {dataset.last_timestep}')
            raise ValueError('Requested dates outside of available dates.')
        return first, last

    def closest_earlier_date(self, date_list, date):
        earlier = filter(lambda d: d <= date, date_list)
        try:
            closest = min(earlier, key=lambda d: abs(d - date))
        except ValueError:
            closest = None
        return closest

    def closest_later_date(self, date_list, date):
        earlier = filter(lambda d: d >= date, date_list)
        try:
            closest = min(earlier, key=lambda d: abs(d - date))
        except ValueError:
            closest = None
        return closest

    def check_date(self, product, subproduct, date):
        ds = Dataset(product=product,
                     subproduct=subproduct,
                     key_file=self.keyfile)

        ds.calculate_timesteps()
        timesteps = ds.timesteps
        date = np.datetime64(date)
        available = date in timesteps
        if not available:
            date1 = self.closest_earlier_date(timesteps, date)
            date2 = self.closest_later_date(timesteps, date)
            print(f'{date} not available. Nearest available dates: {date1} and {date2}')
            raise KeyError(f'{date} not available. Nearest available dates: {date1} and {date2}')
        return available

    def get_data_from_datacube(self, product, subproduct, start, end,
                               latitude, longitude, projection=None):
        ds = Dataset(product=product,
                     subproduct=subproduct,
                     key_file=self.keyfile)

        first, last = self.get_dates(ds, start, end)
        ds.get_data(start=first, stop=last, projection=projection,
                    latlon=[latitude, longitude])

        return ds.data

    def reproject_coords(self, y, x, projection):
        if projection == "British National Grid":
            lat, lon = self.bng_to_latlon(y, x)
        else:
            # Assuming coords in lat lon if not BNG
            lat, lon = y, x
        return lat, lon

    def bng_to_latlon(self, northing, easting):
        """ convert British National Grid easting and northing to latitude and longitude"""
        bng_proj = Proj(
            '+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 +x_0=400000 +y_0=-100000 +ellps=airy +towgs84=446.448,-125.157,542.06,0.1502,0.247,0.8421,-20.4894 +units=m +no_defs=True')
        latlon_proj = Proj(init='epsg:4326')
        lon, lat = transform(bng_proj, latlon_proj, easting, northing)
        return lat, lon

    def data_to_csv(self, product, subproduct,
                    projection, y, x, start, end):

        with self.out:
            clear_output()
            print("Getting data...")

            lat, lon = self.reproject_coords(y, x, projection)
            data = self.get_data_from_datacube(product,
                                               subproduct,
                                               pd.to_datetime(start),
                                               pd.to_datetime(end),
                                               lat,
                                               lon,
                                               projection)
            st = pd.to_datetime(start)
            en = pd.to_datetime(end)
            filename = f"{product}_{subproduct}_{projection}_{y}_{x}" \
                       f"_{st.date()}_{en.date()}.csv"
            data.to_dataframe().to_csv(filename)
            localfile = FileLink(filename)
            display(localfile)

            plt.figure(figsize=(8, 6))
            data.__getitem__(subproduct).plot()
            plt.show()

    def color_map_nesw_compare_reduced(self, product, subproduct, north, east, south,
                                       west, date1, date2):

        with self.out:
            clear_output()
            print("Getting data...")


            PeatHelpers.check(self, north, east, south, west, date1, date1)
            PeatHelpers.check(self, north, east, south, west, date2, date2)
            self.check_date(product, subproduct, date1)
            self.check_date(product, subproduct, date2)

            list_of_results1 = PeatHelpers.get_data_from_datacube_nesw(
                self, product, subproduct, north, east,
                south, west, date1, date1)
            y1 = list_of_results1

            list_of_results2 = PeatHelpers.get_data_from_datacube_nesw(
                self, product, subproduct, north, east,
                south, west, date2, date2)

            y2 = list_of_results2

            fig, axs = plt.subplots(1, 2, figsize=(9, 4))
            y1.__getitem__(subproduct).plot(ax=axs[0])
            y2.__getitem__(subproduct).plot(ax=axs[1])
            plt.tight_layout()
            plt.show()


    def prepare_map(dc, m):

        dc.rectangle = {'shapeOptions': {'color': '#FF0000'}}
        dc.marker = {"shapeOptions": {"fillColor": "#fca45d",
                                      "color": "#fca45d", "fillOpacity": 1.0}}
        dc.polyline = {}
        dc.polygon = {}
        dc.circlemarker = {}


class PeatWidgets(helpers.Widgets):

    
    def product(self):
        projection_list = ['MOD11A1', 'MOD13A2', 'MCD43A3', 'era5']
        return widgets.Dropdown(
            options=projection_list,
            description='Product:',
            layout=self.item_layout,
            disabled=False, )
    
    def get_subproduct_list(self, product):
        if product == 'era5':
            return['skt']
        else:
            return self.search.get_subproduct_list_of_product(product)
    
    def get_projection_widgets(self):
        return self.projection()

    def projection(self):
        projection_list = ['WGS84', 'British National Grid', 'Sinusoidal']
        return widgets.Dropdown(
            options=projection_list,
            description='Projection:',
            layout=self.item_layout,
            disabled=False, )

    def get_x_attributes(self, projection):
        if projection == "British National Grid":
            attributes = {"min": -9999999, "max": 9999999, "description": "Easting (x)"}
        else:
            attributes = {"min": -180, "max": 180, "description": "Longitude (x)"}
        return attributes

    def get_y_attributes(self, projection):
        if projection == "British National Grid":
            attributes = {"min": -9999999, "max": 9999999, "description": "Northing (y)"}
        else:
            attributes = {"min": -90, "max": 90, "description": "Latitude (y)"}
        return attributes


    @staticmethod
    def display_widget_comparison_reduced(product, subproduct, north, east, south,
                                          west, date1,  date2, button, m):

        from ipywidgets import HBox, VBox

        box1 = VBox([product, subproduct, north, east, south,
                     west, date1, date2, button])
        box2 = HBox([box1, m])
        box_layout = widgets.Layout(
            display='flex',
            flex_flow='row',
            align_items='stretch',
            width='100%')
        display(box2)

