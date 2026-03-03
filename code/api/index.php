<?php
header('Content-Type: application/json');

$method = $_SERVER['REQUEST_METHOD'];

if ($method == 'GET') {
    date_default_timezone_set('Africa/Johannesburg');
    $dir   = '/code/venues';
    $files = glob('/code/venues/*-status.txt');
    $venue_list  = [];

    foreach ($files as $file) {
        $time = date('Y-m-d H:i:s', filemtime($file));
        $name = str_replace('-status.txt', '', basename($file));
        $status = trim(file_get_contents($file));

        $venue_list[] = [
            'name' => $name,
            'last_updated' => $time,
            'status' => $status
        ];
    }

    echo json_encode($venue_list, JSON_PRETTY_PRINT);
} else {
    // Handle non-GET requests
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
}
?>