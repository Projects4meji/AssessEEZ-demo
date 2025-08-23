<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class AssessorDocument extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'user_id',
        'qualification_id',
        'attachment',
        'title',
        'created_by',
        'updated_by',
        'status',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
