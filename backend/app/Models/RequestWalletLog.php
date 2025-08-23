<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class RequestWalletLog extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'request_payment_id',
        'remarks',
        'status',
        'created_at',
        'updated_at',
        'deleted_at',
    ];
}
