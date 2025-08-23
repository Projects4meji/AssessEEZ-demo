<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class UpdateUserDetailLog extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'user_id',
        'message',
        'attachment',
        'pre_assessor_id',
        'new_assessor_id',
        'pre_iqa_id',
        'new_iqa_id',
        'pre_qualification_id',
        'new_qualification_id',
        'status',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
