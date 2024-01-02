var stationId = '640';
var previousStationId = '640';
var errorCount = 0;
var selectedNumber = 2;

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
                etaDiv.innerHTML = responseJson.data[0].alltrains[k - 1].eta;
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
        saveUserSettings(stationId, previousStationId, selectedNumber);
        userEntry.value = "";
        const currentDate = new Date();
        const options = { timeZone: 'America/New_York' };
        const currentDateTimeET = currentDate.toLocaleString('en-US', options);     
        document.querySelector('#datetime').textContent = 'ID: ' + stationId + ' ...Station: ' + responseJson.data[0].name + ' ... MTA API Data: ' + responseJson.updated + ' ... Browser Refresh Time in Eastern Time: ' + currentDateTimeET;
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
        setTimeout(() => {console.log("Time out");}, 20000);
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
        console.log("The eta value is ", etaValue);
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
    let trainrowElements = document.querySelectorAll('.trainrow');
    trainrowElements.forEach(function(trainrowElement) {
    let routeElement = trainrowElement.querySelector('.route');
    let routeValue = routeElement.innerText.charAt(0); 
    const routeBackgroundColors = {
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
    let routeBackgroundColor = routeBackgroundColors[routeValue];
    if (!routeValue) {
        routeBackgroundColor = '#000000';
    } 
    let routeTextColor = '#ffffff';
    if (routeValue === 'N' || routeValue === 'Q' || routeValue === 'R' || routeValue === 'W')
    {
        routeTextColor = '#000000'
    }

    console.log("The route value is ", routeValue, ", background is: ",routeBackgroundColors[routeValue],", text is: ", routeTextColor);
    routeElement.style.backgroundColor = `${routeBackgroundColor}`;
    routeElement.style.color = `${routeTextColor}`;
    })
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

function saveUserSettings(cS, pS, sN) {
    console.log("Saving user settings...");
    var userSettings = {
        cookieCurrentStation: cS,
        cookiePreviousStation: pS,
        cookieSelectedNo: sN
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
        editSelectedNumber.value = selectedNumber;
        console.log("Cookie found!", stationId, ", ", previousStationId, ", ", selectedNumber);
    }
}



init().then(result => getUserSettings()).then(result2 => runJob());