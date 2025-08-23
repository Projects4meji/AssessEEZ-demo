<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Communication extends Model
{
    use HasFactory;

    protected $fillable = [
        'id',
        'to_id',
        'topic',
        'message',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'is_seen'
    ];
}
