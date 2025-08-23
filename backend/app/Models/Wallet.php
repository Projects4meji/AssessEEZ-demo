<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Wallet extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'order_id',
        'user_id',
        'amount',
        'remarks',
        'status',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
