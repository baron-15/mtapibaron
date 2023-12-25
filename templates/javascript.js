const stationId = 640;
const mtaRoute0 = document.getElementById('route0');
const mtaTerminal0 = document.getElementById('terminal0');
const mtaEta0 = document.getElementById('eta0');
const mtaRoute1 = document.getElementById('route1');
const mtaTerminal1 = document.getElementById('terminal1');
const mtaEta1 = document.getElementById('eta1');

async function loadSomeDisplay (stationId) {
    // const API_URL = `http://mta-api-project.uc.r.appspot.com/by-id/${stationId}`;
    const API_URL = `http://127.0.0.1:5000/by-id/${stationId}`;
    await fetch(API_URL)
    .then(response => response.json())
    .then(responseJson => {
        
        mtaRoute0.innerHTML = responseJson.data[0].alltrains[0].route;
        mtaTerminal0.innerHTML = responseJson.data[0].alltrains[0].terminalName;
        mtaEta0.innerHTML = responseJson.data[0].alltrains[0].eta;
        mtaEta0.innerHTML += ' min';
        mtaRoute1.innerHTML = responseJson.data[0].alltrains[1].route;
        mtaTerminal1.innerHTML = responseJson.data[0].alltrains[1].terminalName;
        mtaEta1.innerHTML = responseJson.data[0].alltrains[1].eta;
        mtaEta1.innerHTML += ' min';
        const currentDate = new Date();
        const options = { timeZone: 'America/New_York' };
        const currentDateTimeET = currentDate.toLocaleString('en-US', options);     
        document.querySelector('#datetime').textContent = 'Station: ' + responseJson.data[0].name + ' ... MTA API Data: ' + responseJson.updated + ' ... Browser Refresh Time in Eastern Time: ' + currentDateTimeET;
    })
}

loadSomeDisplay(stationId).then(
    testBlinking => arrivalUpdate()).then(testColoring => routeUpdate()).catch((err) => {
    console.error(err)
    });

setInterval(function () {
    loadSomeDisplay(stationId).then(
    testBlinking => arrivalUpdate()).then(testColoring => routeUpdate()).catch((err) => {
    console.error(err)
    });
}, 15000);

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
        var routeValue = routeElement.innerText; 
        
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
