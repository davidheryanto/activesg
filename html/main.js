var availability, venues;
var map, markers = [], infoWindow;

async.waterfall([
  loadData,
  parseQueryString,
  initEventListeners,
  initMap
])

function initEventListeners(callback) {
  $('#btn-next-date').on('click', function (e) {
    e.preventDefault();
    var nextOption = $('#select-date').find(':selected').next();
    if (nextOption.length > 0) {
      nextOption.prop('selected', true).change();
      window.history.pushState(null, null, '?date=' + nextOption.text())
    }
  })

  $('#btn-prev-date').on('click', function (e) {
    e.preventDefault();
    var prevOption = $('#select-date').find(':selected').prev();
    if (prevOption.length > 0) {
      prevOption.prop('selected', true).change();
      window.history.pushState(null, null, '?date=' + prevOption.text())
    }
  })

  $('#select-date').on('change', function () {
    loadMarkers();
  })

  callback(null);
}

function loadData(callback) {
  async.parallel([
    queryVenues,
    queryAvailability,
  ], function () {
    callback(null);
  })
}

function parseQueryString(callback) {
  if (location.search.indexOf('?date') >= 0) {
    date = location.search.substr(6, 10);
    var selector = '#select-date option[value=' + date + ']';
    $(selector).prop('selected', true);
  }
  callback(null);
}

function queryVenues(callback) {
  $.ajax({
    url: 'venues.json',
    success: function (data) {
      venues = data;
      callback(null);
    }
  })
}

function queryAvailability(callback) {
  $.ajax({
    url: 'availability.json',
    success: function (data) {
      availability = data;
      var selectDate = $('#select-date');
      for (var date in availability) {
        $('<option/>', {
          text: date,
          value: date
        }).appendTo(selectDate);
      }
      callback(null);
    }
  })
}

function loadMarkers() {
  clearMarkers();

  var selectedDate = $('#select-date').find(':selected').text();
  var slots = availability[selectedDate];

  for (var venue_id in slots) {
    var contentString = '<div><strong>' + venues[venue_id].name + '</strong></div>';
    for (var court in slots[venue_id]) {
      var line = '<div>' + court + ':';
      slots[venue_id][court].forEach(function (timing) {
        line += ' ' + timing.substr(0, timing.lastIndexOf(':'));
      })
      contentString += line + '</div>'
    }

    var marker = new google.maps.Marker({
      position: {lat: venues[venue_id].lat, lng: venues[venue_id].lng},
      map: map,
      contentString: contentString
    })

    marker.addListener('mouseover', function () {
      infoWindow.setContent(this.contentString);
      infoWindow.open(map, this);
    });

    marker.addListener('mouseout', function () {
      infoWindow.close()
    });

    markers.push(marker);
  }
}

function clearMarkers() {
  if (markers.length > 0) {
    markers.forEach(function (marker) {
      google.maps.event.clearListeners(marker, 'mouseover');
      google.maps.event.clearListeners(marker, 'mouseout');
      marker.setMap(null);
    })
    markers = [];
  }
}

function initMap(callback) {
  var singapore = {lat: 1.3521, lng: 103.8198};
  map = new google.maps.Map(document.getElementById('map'), {
    zoom: 12,
    center: singapore
  });
  infoWindow = new google.maps.InfoWindow();
  loadMarkers();
  callback(null);
}