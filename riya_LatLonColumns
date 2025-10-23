function GOOGLEMAPS_LATLONG(address) {
  if (!address) return "";
  var geocoder = Maps.newGeocoder();
  var response = geocoder.geocode(address);
  if (response.status === 'OK' && response.results.length > 0) {
    var lat = response.results[0].geometry.location.lat;
    var lng = response.results[0].geometry.location.lng;
    return lat + "," + lng;
  }
  return "Not found";
}


