<?php

$method = $_SERVER['REQUEST_METHOD'];

if ($method == 'POST') {

    $lsname = "lecturesight";

    if (isset($_POST['name'])) {
        $lsname = $_POST['name'];
    } else {
        http_response_code(400);
        die('No name field provided');
    }

    if (!preg_match("/^([a-zA-Z0-9_-]){1,30}$/", $lsname)) {
        http_response_code(400);
        die('Invalid name $lsname');
    }

    $uploaddir = "/code/venues/{$lsname}";

    // Status
    if(isset($_POST['status'])) {
        $data = $_POST['status'];
        $ret = file_put_contents("{$uploaddir}-status.txt", $data, LOCK_EX);
        if($ret === false) {
        http_response_code(500);
            die('There was an error writing this file');
        }
    }

    // Metrics
    if(isset($_POST['metrics'])) {
        $data = $_POST['metrics'];
        $ret = file_put_contents("{$uploaddir}-metrics.json", $data, LOCK_EX);
        if($ret === false) {
            http_response_code(500);
            die('There was an error writing this file');
        }
    }

    // Scene profile
    if(isset($_POST['profile'])) {
        $data = $_POST['profile'];
        $ret = file_put_contents("{$uploaddir}-profile.scn", $data, LOCK_EX);
        if($ret === false) {
            http_response_code(500);
            die('There was an error writing this file');
        }
    }

    // Overview image
    if (move_uploaded_file($_FILES['overview-image']['tmp_name'], $uploaddir . '-overview.png')) {
        echo "File is valid, and was successfully uploaded.\n";
    } else {
        http_response_code(500);
        echo "Upload failed";
    }
} else {
    date_default_timezone_set('Africa/Johannesburg');
    $dir   = '/code/venues';
    $files = glob('/code/venues/*-status.txt');
    $venue_list  = [];

    foreach ($files as $file) {

        $time = date('Y-m-d H:i:s', filemtime($file));
        $name = str_replace('-status.txt', '', basename($file));
        $status = file_get_contents($file);

        $venue_list[$name] = [$time, $status];
    }

    $fp = fopen('/code/venues.json', 'w');
    if (fwrite($fp, json_encode($venue_list))) {
        print "1";
    }
    fclose($fp);
}
?>
