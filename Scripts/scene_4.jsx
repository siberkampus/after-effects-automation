
(function () {
    app.beginUndoGroup("AI Documentary Scene");
    var SCENE_NAME = "Scene_4_parallax_slide";
    var SCENE_TITLE = "SHIELD ACTIVE";
    var IMAGE_PATH = "";
    var DURATION = 7.0;
    var W = 1920;
    var H = 1080;
    var FPS = 30;
    var PROJECT_PATH = "C:\\Users\\ACER\\Documents\\AE_AI_AUTOMATION\\Projects\\documentary_project.aep";
    var STYLE = "parallax_slide";

    try {
        var comp = app.project.items.addComp(SCENE_NAME, W, H, 1, DURATION, FPS);
        comp.bgColor = [0.02, 0.02, 0.02];
        comp.layers.addSolid([0.02, 0.02, 0.02], "Background", W, H, 1, DURATION);

        var imageLayer = null;
        if (IMAGE_PATH !== "") {
            var imageFile = new File(IMAGE_PATH);
            if (imageFile.exists) {
                var footage = app.project.importFile(new ImportOptions(imageFile));
                imageLayer = comp.layers.add(footage);
                imageLayer.startTime = 0; imageLayer.inPoint = 0; imageLayer.outPoint = DURATION;
                var scaleX = W / footage.width * 100;
                var scaleY = H / footage.height * 100;
                var scale = Math.max(scaleX, scaleY);
                imageLayer.property("ADBE Transform Group").property("ADBE Scale").setValue([scale, scale]);
            }
        }

        // Sinematik Siyah Bantlar
        var topBar = comp.layers.addSolid([0, 0, 0], "Top Bar", W, 120, 1, DURATION);
        topBar.property("ADBE Transform Group").property("ADBE Position").setValue([W / 2, 60]);
        var bottomBar = comp.layers.addSolid([0, 0, 0], "Bottom Bar", W, 120, 1, DURATION);
        bottomBar.property("ADBE Transform Group").property("ADBE Position").setValue([W / 2, H - 60]);

        else if (STYLE === "parallax_slide" && imageLayer) {
            imageLayer.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(0, [W*0.6, H/2]);
            imageLayer.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(1.2, [W/2, H/2]);
            imageLayer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(0, [120, 120]);
            imageLayer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(DURATION, [100, 100]);
            
            var title = comp.layers.addText(SCENE_TITLE);
            var td = title.property("ADBE Text Properties").property("ADBE Text Document").value;
            td.fontSize = 90; td.font = "Arial-BoldMT"; td.fillColor = [0.9, 0.8, 0.3];
            title.property("ADBE Text Properties").property("ADBE Text Document").setValue(td);
            title.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(0.5, [W/2, H*0.75]);
            title.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(0, [-W/2, H*0.75]);
        }

        if (PROJECT_PATH !== "") { app.project.save(new File(PROJECT_PATH)); }
        app.endUndoGroup();
    } catch (e) {
        app.endUndoGroup(); alert("Hata: " + e.toString());
    }
})();
