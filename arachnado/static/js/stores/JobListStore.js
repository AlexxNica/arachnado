require("babel-core/polyfill");
var Reflux = require("reflux");
var { FancyWebSocket } = require("../utils/FancyWebSocket");
var API = require("../utils/ArachnadoAPI");


export var Actions = Reflux.createActions([
    "setAll",
    "updateStats",
    "startCrawl",
    "stopCrawl",
    "pauseCrawl",
    "resumeCrawl",
]);


export var store = Reflux.createStore({
    init: function () {
        this.jobs = [];
        this.listenTo(Actions.setAll, this.onSetAll);
        this.listenTo(Actions.updateStats, this.onUpdateStats);
        this.listenTo(Actions.startCrawl, this.doStartCrawl);
        this.listenTo(Actions.stopCrawl, this.doStopCrawl);
        this.listenTo(Actions.pauseCrawl, this.doPauseCrawl);
        this.listenTo(Actions.resumeCrawl, this.doResumeCrawl);
    },

    getInitialState: function () {
        return this.jobs;
    },
    
    onSetAll: function (jobs) {
        this.jobs = jobs;
        this.trigger(jobs);
    },

    onUpdateStats: function (crawlId, changes) {
        this.jobs.filter(job => job.id == crawlId).forEach(job => {
            job.stats = Object.assign(job.stats || {}, changes);
        });
        this.trigger(this.jobs);
    },

    doStartCrawl: function (domain, options) {
        API.startCrawl(domain, options);
    },

    doStopCrawl: function (jobId) {
        API.stopCrawl(jobId);
    },

    doPauseCrawl: function (jobId) {
        API.pauseCrawl(jobId);
    },

    doResumeCrawl: function (jobId) {
        API.resumeCrawl(jobId);
    }
});


var socket = FancyWebSocket.instance();
socket.on("jobs:state", (jobs) => {
    console.log("jobs:state", jobs);
    Actions.setAll(jobs);
});

socket.on("stats:changed", (data) => {
    var [crawlId, changes] = data;
    Actions.updateStats(crawlId, changes);
    //console.log("stats:changed", crawlId, changes);
});

Actions.setAll(window.INITIAL_DATA.jobs);

