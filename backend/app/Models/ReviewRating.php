<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class ReviewRating extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'order_id',
        'user_id',
        'review',
        'condition_rating',
        'seller_communication_rating',
        'sending_time_rating',
        'size_rating',
        'city',
        'type',
        'deleted_at'
    ];
}
