// Keep startup wiring separate from feature files so page initialization stays easy to trace.
setPanel("panel-solve");
clearPracticeDisplay();
resetSolveAttachment();
queueSolveChatRender();
refreshCompactSelectWidths();
window.addEventListener("resize", refreshCompactSelectWidths);
loadHealth();
loadMatlabStatus();
loadWrongQuestions();
renderSimulationCoachLog();
loadSimulationLabs();
