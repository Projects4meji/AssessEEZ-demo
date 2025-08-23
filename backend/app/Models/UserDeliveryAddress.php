<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class UserDeliveryAddress extends Model
{
    use HasFactory, SoftDeletes;

    protected $table = 'user_delivery_addresses';

    protected $fillable = [
        'user_id',
        'location',
        'country',
        'city',
        'lat',
        'lon',
        'is_default',
        'deleted_at'
    ];
}
