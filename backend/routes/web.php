<?php

use App\Http\Controllers\API\OrderController;
use App\Http\Controllers\AuthController;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return view('welcome');
});

Route::get('/payment_webhook', function () {
    // $hash = strtoupper(
    //     md5(
    //         '1227501' .
    //             'ItemNo12345' .
    //             number_format(1000, 2, '.', '') .
    //             'LKR' .
    //             strtoupper(md5('MzcyNjExMDI3NzQwMTI2MDY0MDIxMTU5MTAyODk2MzE3OTU0MjI2OA=='))
    //     )
    // );
    // dd($hash);
    return view('payment');
});

// Route::get('/login', function () {
//     return view('welcome');
// })->name('login');

Route::get('login', [AuthController::class, 'login'])->name('login');
