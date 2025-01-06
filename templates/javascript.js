var stationId = '640';
var previousStationId = '640';
var errorCount = 0;
var selectedNumber = 2;
var displayStationBlock = 0;
var routeBackgroundColors = {
    A: '#0039a6',
    C: '#0039a6',
    E: '#0039a6',
    B: '#FF6319',
    D: '#FF6319',
    F: '#FF6319',
    M: '#FF6319',
    G: '#6CBE45',
    J: '#996633',
    Z: '#996633',
    L: '#A7A9AC',
    N: '#FCCC0A',
    Q: '#FCCC0A',
    R: '#FCCC0A',
    W: '#FCCC0A',
    S: '#808183',
    1: '#EE352E',
    2: '#EE352E',
    3: '#EE352E',
    4: '#00933C',
    5: '#00933C',
    6: '#00933C',
    7: '#B933AD'
}

async function init() {
    selectedNumber = parseInt(document.getElementById("noOfTrainsEntry").value);
    return;
}


async function loadSomeDisplay (stationId) {
    console.log("Loading display for stationID ", stationId);
    const API_URL = `https://mta-api-project.uc.r.appspot.com/by-id/${stationId}`;
    //const API_URL = `http://127.0.0.1:5000/by-id/${stationId}`;
    if ((stationId.length > 3) || (isNaN(stationId[1])) || (isNaN(stationId[2])))
    {
        console.log(stationId, 'did not pass the eye test.');
        throw new Error("It did not pass the eye test.");
    }
    
    await fetch(API_URL)
    .then(response => response.json())
    .then(responseJson => {
        let currentDate = new Date();
        let options = { timeZone: 'America/New_York' };
        let currentDateTimeET = currentDate.toLocaleString('en-US', options);
        selectedNumber = parseInt(document.getElementById("noOfTrainsEntry").value);
        let noOfTrains = Object.keys(responseJson.data[0].alltrains).length;
        document.getElementById("trainBlock").innerHTML = "";
        for (let k = 1; k <= selectedNumber; k++) {
            let trainrowDiv = document.createElement("div");
            trainrowDiv.className = "trainrow";
            trainrowDiv.id = "trainrow" + k;

            let numDiv = document.createElement("div");
            numDiv.className = "num";
            numDiv.id = "num" + k;
            numDiv.innerHTML = k +".";

            let routeDiv = document.createElement("div");
            routeDiv.className = "route";
            routeDiv.id = "route" + k;

            let routeTextDiv = document.createElement("div");
            routeTextDiv.className = "routeText";
            routeTextDiv.id = "routeText" + k;

            routeDiv.appendChild(routeTextDiv);

            let terminalDiv = document.createElement("div");
            terminalDiv.className = "terminal";
            terminalDiv.id = "terminal" + k;

            let etaDiv = document.createElement("div");
            etaDiv.className = "eta";
            etaDiv.id = "eta" + k;

            trainrowDiv.appendChild(numDiv);
            trainrowDiv.appendChild(routeDiv);
            trainrowDiv.appendChild(terminalDiv);
            trainrowDiv.appendChild(etaDiv);
            document.getElementById("trainBlock").appendChild(trainrowDiv);

            if (noOfTrains >= k) {
                routeTextDiv.innerHTML = responseJson.data[0].alltrains[k - 1].route.charAt(0);
                terminalDiv.innerHTML = responseJson.data[0].alltrains[k - 1].terminalName;
                let etaString = responseJson.data[0].alltrains[k - 1].time;
                let eta = new Date(etaString);
                etaDiv.innerHTML = timeDifference(currentDate, eta);
                etaDiv.innerHTML += ' min';
                if (responseJson.data[0].alltrains[k-1].route.slice(-1) == "X")
                {
                    routeDiv.classList.remove('circle');
                    routeDiv.classList.add('diamond');
                }
                else
                {
                    routeDiv.classList.remove('diamond');
                    routeDiv.classList.add('circle');
                }
            }

            else {
                    routeTextDiv.innerHTML = "";
                    terminalDiv.innerHTML = "No scheduled";
                    etaDiv.innerHTML = "";
                }
        }
        /*
        const mtaRouteText0 = document.getElementById('routeText0');
        const mtaTerminal0 = document.getElementById('terminal0');
        const mtaEta0 = document.getElementById('eta0');
        const mtaRouteText1 = document.getElementById('routeText1');
        const mtaTerminal1 = document.getElementById('terminal1');
        const mtaEta1 = document.getElementById('eta1');
        const mtaRoute0 = document.getElementById('route0');
        const mtaRoute1 = document.getElementById('route1');
        var noOfTrains = Object.keys(responseJson.data[0].alltrains).length;
        var svc0;
        console.log("Number of trains from API is: ", noOfTrains);
        if (noOfTrains >=1) {
            mtaRouteText0.innerHTML = responseJson.data[0].alltrains[0].route.charAt(0);
            mtaTerminal0.innerHTML = responseJson.data[0].alltrains[0].terminalName;
            mtaEta0.innerHTML = responseJson.data[0].alltrains[0].eta;
            mtaEta0.innerHTML += ' min';
            //for future use to display exp box
            svc0 = responseJson.data[0].alltrains[0].service;
            if (responseJson.data[0].alltrains[0].route.slice(-1) == "X")
            {
                mtaRoute0.classList.remove('circle');
                mtaRoute0.classList.add('diamond');
            }
            else
            {
                mtaRoute0.classList.remove('diamond');
                mtaRoute0.classList.add('circle');
            }
        }
        if (noOfTrains >=2) {
            mtaRouteText1.innerHTML = responseJson.data[0].alltrains[1].route.charAt(0);
            mtaTerminal1.innerHTML = responseJson.data[0].alltrains[1].terminalName;
            mtaEta1.innerHTML = responseJson.data[0].alltrains[1].eta;
            mtaEta1.innerHTML += ' min';
            svc1 = responseJson.data[0].alltrains[1].service;
            if (responseJson.data[0].alltrains[1].route.slice(-1) == "X")
            {
                mtaRoute1.classList.remove('circle');
                mtaRoute1.classList.add('diamond');
            }
            else
            {
                mtaRoute1.classList.remove('diamond');
                mtaRoute1.classList.add('circle');
            }
        }
        if (noOfTrains == 0) {
            mtaRouteText0.innerHTML = "";
            mtaTerminal0.innerHTML = "No upcoming train";
            mtaEta0.innerHTML = "";
            mtaRouteText1.innerHTML = "";
            mtaTerminal1.innerHTML = "No upcoming train";
            mtaEta1.innerHTML = "";
        }
        */
        previousStationId = stationId;
        saveUserSettings(stationId, previousStationId, selectedNumber, displayStationBlock);
        userEntry.value = "";
        document.querySelector('#datetime').textContent = 'ID: ' + stationId  + ' ... MTA API Data: ' + responseJson.updated + ' ... Browser Refresh Time: ' + currentDateTimeET + ' ET';
        
        const rawStationName = responseJson.data[0].name;
        const stationNameArr = rawStationName.split("|");
        document.querySelector('#stationName').textContent = stationNameArr[0] + ' Station';
        for (let i = 1; i < stationNameArr.length; i++) {
            let altNameBlock = document.createElement("div");
            altNameBlock.id = "stationNameAlt";
            altNameBlock.innerHTML = stationNameArr[i] + ' Station';
            document.querySelector('#stationName').appendChild(altNameBlock);
        }

        let rawRoutes = responseJson.data[0].routes;
        rawRoutes = routeOrderSort(rawRoutes);
        let noOfRoutes = rawRoutes.length;
        document.getElementById("allRoutes").innerHTML = "";

        if (noOfRoutes > 0) {
            document.getElementById("allRoutes").style.display = "grid"; 
          } else {
            document.getElementById("allRoutes").style.display = "none";
          }
          
        for (let k = 1; k <= noOfRoutes; k++) {
            let routeBlock = document.createElement("div");
            routeBlock.className = "route";
            routeBlock.id = "stationRouteText" + k;
            let routeTextBlock = document.createElement("div");
            routeTextBlock.className = "routeText";
            routeTextBlock.id = "routeText" + k;
            routeTextBlock.innerHTML = rawRoutes[k - 1].charAt(0);
            routeBlock.appendChild(routeTextBlock);
            if (rawRoutes[k-1].slice(-1) == "X")
                {
                    routeBlock.classList.remove('circle');
                    routeBlock.classList.add('diamond');
                }
                else
                {
                    routeBlock.classList.remove('diamond');
                    routeBlock.classList.add('circle');
                }
            document.getElementById("allRoutes").appendChild(routeBlock);
        }
    })
}

function runJobOnce() {
    console.log("Running job");
    loadSomeDisplay(stationId).then(
        testBlinking => arrivalUpdate()).then(testColoring => routeUpdate()).catch((err) => {
    errorCount += 1;
    console.log("One error! " + err + " for station " + stationId );
    if (errorCount >= 20) {
        console.log("Too many errors. Abort. Delaying for 15s.");
        setTimeout(() => {
            console.log("Resetting to station 640.");
            stationId = 640;
            previousStationId = 640;
            userEntry.value = "";
        }, 15000);
        throw new Error("Something went wrong repeatedly.");
    }
    let userEntry = document.getElementById("stopIdEntry");

    // added the stationId != previousId as hover away and submit enter may trigger two actions
    // which may cause invalid display to be incorrect
    if ((userEntry) && (stationId != previousStationId)) { 
        userEntry.placeholder = `${stationId} invalid`;
        userEntry.value = "";
    }
    stationId = previousStationId;
    runJobOnce();
    return false;
    });
}

function runJob() {
    runJobOnce();
    var intervalId = setInterval(function () {
        console.log("Running job from interval.");
        runJobOnce();
    }, 15000);
}

function arrivalUpdate () {
    let trainrowElements = document.querySelectorAll('.trainrow');
    trainrowElements.forEach(function(trainrowElement) {
        let etaElement = trainrowElement.querySelector('.eta');
        var etaValue = etaElement.innerText; 
        if (etaValue === '0 min') {
            trainrowElement.classList.add('arrivalyellow');
            etaElement.classList.add('blink');
        }

        else {
            trainrowElement.classList.remove('arrivalyellow');
            etaElement.classList.remove('blink');
        }
    })

}   

function routeUpdate () {
    let routeElements = document.querySelectorAll('.route');
    routeElements.forEach(function(routeElement) {
    let routeValue = routeElement.innerText.charAt(0); 
    let routeBackgroundColor = routeBackgroundColors[routeValue];
    if (!routeValue) {
        routeBackgroundColor = '#000000';
    } 
    let routeTextColor = '#ffffff';
    if (routeValue === 'N' || routeValue === 'Q' || routeValue === 'R' || routeValue === 'W')
    {
        routeTextColor = '#000000'
    }
    
    routeElement.style.backgroundColor = `${routeBackgroundColor}`;
    routeElement.style.color = `${routeTextColor}`;
    })
    errorCount = 0;
}

var stopForm = document.getElementById("stopIdForm");
var userEntry = document.getElementById("stopIdEntry");
stopForm.addEventListener("submit", (e) => {
    e.preventDefault();
    processStopIdEntry(e)
});

userEntry.addEventListener("change", (e) => {
    e.preventDefault();
    processStopIdEntry(e)
});

function processStopIdEntry(e) {
    if (userEntry.value == '') {
        return false;
    }
    else {
        console.log("User entry: ", userEntry.value);
        stationId = userEntry.value.toUpperCase();
        runJobOnce();
        saveUserSettings(stationId, previousStationId, selectedNumber);
        userEntry.placeholder = `640, 127, 228, 631...`;
    }
}

function saveUserSettings(cS, pS, sN, sB) {
    console.log("Saving user settings...");
    var userSettings = {
        cookieCurrentStation: cS,
        cookiePreviousStation: pS,
        cookieSelectedNo: sN,
        cookieDisplayStationBlock:sB
    };

    var userSettingsJSON = JSON.stringify(userSettings);
    document.cookie = 'userSettings=' + encodeURIComponent(userSettingsJSON) + '; expires=' + new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toUTCString() + '; path=/';
}

function getUserSettings() {
    console.log("Getting user settings...");
    var cookies = document.cookie.split(';');
    var userSettingsCookie = cookies.find(cookie => cookie.trim().startsWith('userSettings='));

    if (userSettingsCookie) {
        var userSettingsJSON = decodeURIComponent(userSettingsCookie.split('=')[1]);
        var userSettings = JSON.parse(userSettingsJSON);
        let editSelectedNumber = document.getElementById("noOfTrainsEntry");
        stationId = userSettings.cookieCurrentStation;
        previousStationId = userSettings.cookiePreviousStation;
        selectedNumber = userSettings.cookieSelectedNo;
        displayStationBlock = userSettings.cookieDisplayStationBlock;
        let stationBlock = document.getElementById("stationBlock");
        let checkbox = document.getElementById("toggleStationBlock");
        if (displayStationBlock) {
            stationBlock.style.display = "grid";
            checkbox.checked = true;
          } else {
            stationBlock.style.display = "none";
            checkbox.checked = false;
          }
        editSelectedNumber.value = selectedNumber;
        console.log("Cookie found!", stationId, ", ", previousStationId, ", ", selectedNumber, ",", displayStationBlock);
    }
}

function toggleStationBlock() {
    let stationBlock = document.getElementById("stationBlock");
    let checkbox = document.getElementById("toggleStationBlock");

    if (checkbox.checked) {
      stationBlock.style.display = "grid";
      displayStationBlock = 1;
    } else {
      stationBlock.style.display = "none";
      displayStationBlock = 0;
    }
    saveUserSettings(stationId, previousStationId, selectedNumber, displayStationBlock);
  }

function loadURLandSetStationId() {
    /* let currentURL = window.location.href;
    let pathArray = window.location.pathname.split('/');
    if (pathArray[-1].length === 3 || pathArray[-1].length === 4) {
        stationId = pathArray[-1];
        console.log('Detected custom path: ', stationId);
        window.location.replace(pathArray[0]);
    }
    */
}

init().then(result => getUserSettings()).then(result2 => runJob());

// To mock the order of route display based on Times Square (ACENQRWS1237) and Grand Central (4567S) to blend S in middle
// I had to write two separate sort functions to run based on if a letter other S exists
// ChatGPT struggled to lump it into one function
// Unretired as it ran slower in Python backend using mtapi.py
function routeOrderSort(arr) {
    function customComparator1(a, b) {
        if (a[0].match(/[A-Za-z]/) && a[0] !== 'S') {
            if (b[0].match(/[A-Za-z]/) && b[0] !== 'S') {
                return a.localeCompare(b);
            } else {
                return -1;
            }
        } else if (a[0] === 'S') {
            if (b[0] === 'S') {
                return 0;
            } else if (b[0].match(/[A-Za-z]/)) {
                return 1;
            } else {
                return -1;
            }
        } else if (a[0].match(/\d/)) {
            if (b[0].match(/\d/)) {
                return a.localeCompare(b);
            } else {
                return 1;
            }
        } else if (b[0].match(/\d/)) {
            return -1;
        } else {
            return 1;
        }
    }

    function customComparator2(a, b) {
        if (a[0].match(/\d/) && b[0].match(/\d/)) {
            return a.localeCompare(b);
        } else if (a[0].match(/\d/)) {
            return -1;
        } else {
            return 1;
        }
    }

    function uniqueFirstCharacters(a) {
        let uniqueChars = new Set();
        a.forEach(str => {
          let firstChar = str.charAt(0);
          uniqueChars.add(firstChar);
        });
        return Array.from(uniqueChars);
    }

    arr = uniqueFirstCharacters(arr);

    if (arr.some(item => item[0].match(/[A-Za-z]/) && item[0] !== 'S')) {
        return arr.sort(customComparator1);
    }

    else {
        return arr.sort(customComparator2);
    }
}

function timeDifference (startTime, endTime) {
    const timeDifference = endTime.getTime() - startTime.getTime();
    const minuteDifference = Math.round(timeDifference / (1000 * 60));
    if (minuteDifference > 99){
        return "99+";
    }
    else if (minuteDifference == -1) {
        return "0";
    }
    else if (minuteDifference <= -2) {
        let options = { timeZone: 'America/New_York' };
        let startTimeET = startTime.toLocaleString('en-US', options);
        let endTimeET = endTime.toLocaleString('en-US', options);
        console.log("Bad minute difference: ", minuteDifference);
        console.log("Start time: ", startTimeET);
        console.log("End time: ", endTimeET);
        return "ERR";
    }
    else {
        return minuteDifference;
    }
}