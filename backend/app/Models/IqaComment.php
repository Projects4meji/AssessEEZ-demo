<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class IqaComment extends Model
{
    use HasFactory, SoftDeletes;

    protected $table = 'iqa_comments';

    protected $fillable = [
        'id',
        'qualification_id',
        'learner_id',
        'ac_id',
        'comments',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
