<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class QualificationLo extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'qualification_id',
        'unit_id',
        'lo_number',
        'lo_detail',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
