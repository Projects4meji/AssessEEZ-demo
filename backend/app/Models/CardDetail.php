<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class CardDetail extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'user_id',
        'card_no',
        'card_holder_name',
        'expire_date',
        'card_type',
        'is_default',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
