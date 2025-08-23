<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class RequestPayment extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'wallet_ids',
        'status',
        'created_at',
        'updated_at',
        'deleted_at',
        'amount',
        'user_id'
    ];
}
