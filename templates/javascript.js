var stationId = '640';
var previousStationId = '640';
var errorCount = 0;
const trainCount = 2;


async function loadSomeDisplay (stationId) {
    const API_URL = `https://mta-api-project.uc.r.appspot.com/by-id/${stationId}`;
    //const API_URL = `http://127.0.0.1:5000/by-id/${stationId}`;
    if ((stationId.length > 3) || (isNaN(stationId[1])) || (isNaN(stationId[2])))
    {
        console.log(stationId, 'did not pass the eye test.');
    }
    
    await fetch(API_URL)
    .then(response => response.json())
    .then(responseJson => {  
        const mtaRouteText0 = document.getElementById('routeText0');
        const mtaTerminal0 = document.getElementById('terminal0');
        const mtaEta0 = document.getElementById('eta0');
        const mtaRouteText1 = document.getElementById('routeText1');
        const mtaTerminal1 = document.getElementById('terminal1');
        const mtaEta1 = document.getElementById('eta1');
        mtaRouteText0.innerHTML = responseJson.data[0].alltrains[0].route.charAt(0);
        mtaTerminal0.innerHTML = responseJson.data[0].alltrains[0].terminalName;
        mtaEta0.innerHTML = responseJson.data[0].alltrains[0].eta;
        mtaEta0.innerHTML += ' min';
        mtaRouteText1.innerHTML = responseJson.data[0].alltrains[1].route.charAt(0);
        mtaTerminal1.innerHTML = responseJson.data[0].alltrains[1].terminalName;
        mtaEta1.innerHTML = responseJson.data[0].alltrains[1].eta;
        mtaEta1.innerHTML += ' min';
        //for future use to display exp box
        var svc0 = responseJson.data[0].alltrains[0].service;
        var svc1 = responseJson.data[0].alltrains[1].service;
        //to decide if we need a diamond later
        const mtaRoute0 = document.getElementById('route0');
        const mtaRoute1 = document.getElementById('route1');
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

        const currentDate = new Date();
        const options = { timeZone: 'America/New_York' };
        const currentDateTimeET = currentDate.toLocaleString('en-US', options);     
        document.querySelector('#datetime').textContent = 'ID: ' + stationId + ' ...Station: ' + responseJson.data[0].name + ' ... MTA API Data: ' + responseJson.updated + ' ... Browser Refresh Time in Eastern Time: ' + currentDateTimeET;
    })
}

function runJobOnce() {
    loadSomeDisplay(stationId).then(
        testBlinking => arrivalUpdate()).then(testColoring => routeUpdate()).catch((err) => {
    errorCount += 1;
    if (errorCount >= 20) {
        console.log("Too many errors. Abort. Delaying for 15s.");
        setTimeout(() => {}, "15000");
        throw new Error("Something went wrong repeatedly.");
    }
    let userEntry = document.getElementById("stopIdEntry");
    if (userEntry) {
        userEntry.placeholder = `Invalid station: ${stationId}`;
    }
    stationId = previousStationId;
    runJobOnce();
    });
}

function runJob() {
    runJobOnce();
    var intervalId = setInterval(function () {
        runJobOnce();
    }, 15000);
}

runJob();

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

let stopForm = document.getElementById("stopIdForm");
stopForm.addEventListener("submit", (e) => {
  e.preventDefault();
  let userEntry = document.getElementById("stopIdEntry");
  if (userEntry.value == '') {
    alert("Ensure you input a value");
  }
  else {
    console.log("User entry: ", userEntry.value);
    previousStationId = stationId;
    stationId = userEntry.value;
  }
  userEntry.value = "";
  runJobOnce();
});